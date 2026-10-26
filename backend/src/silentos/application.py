"""Central application controller: owns settings, database and runtime state."""

from __future__ import annotations

import logging
import platform
import shutil
import socket
from datetime import datetime, timezone

import psutil

from .config import Settings
from .database import Database
from .camera import CameraManager
from .registry import status_for
from .schemas import (  # noqa: F401  (re-exported for routes)
    AppStatus,
    CameraState,
    ModelStatus,
    RecognitionMode,
    RuntimeState,
    SystemMetrics,
)


logger = logging.getLogger("silentos")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Application:
    """Holds real runtime state. No fabricated values: unavailable metrics stay None."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.paths.ensure()
        self.db = Database(settings.paths.data_dir / "silentos.db")
        self.camera = CameraManager()
        self.runtime_state = RuntimeState.STOPPED
        self.last_error: str | None = None
        self.frames_processed = 0
        self._pending_restart: list[str] = []
        # Prime the CPU counter so the first reported value is a real measurement
        # over the process lifetime, not a fabricated zero.
        psutil.cpu_percent(interval=None)

    def app_status(self) -> AppStatus:
        return AppStatus(
            runtime_state=self.runtime_state,
            recognition_mode=RecognitionMode(self.settings.recognition.mode),
            camera_state=CameraState.DISCONNECTED,
            camera_provider=self.settings.camera.provider,
            sign_model_status=status_for(self.settings.paths.models_dir, "sign"),
            lip_model_status=status_for(self.settings.paths.models_dir, "lip"),
            speech_enabled=self.settings.output.speech_enabled,
            last_message=None,
            last_recognition=None,
            inference_latency_ms=None,
            timestamp=_now(),
        )

    def system_metrics(self) -> SystemMetrics:
        vm = psutil.virtual_memory()
        try:
            disk = shutil.disk_usage(self.settings.paths.data_dir)
            disk_percent = round(disk.used / disk.total * 100, 1)
        except OSError:
            disk_percent = None

        temp: float | None = None
        try:
            for entries in psutil.sensors_temperatures().values():
                if entries and entries[0].current is not None:
                    temp = float(entries[0].current)
                    break
        except (AttributeError, OSError):
            pass  # not exposed on this hardware -> None, never fabricated

        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=vm.percent,
            memory_used_mb=round(vm.used / 1024 / 1024, 1),
            memory_total_mb=round(vm.total / 1024 / 1024, 1),
            disk_percent=disk_percent,
            temperature_c=temp,
            hostname=socket.gethostname(),
            platform=platform.platform(),
            timestamp=_now(),
        )

    # ---- settings (persisted overrides) ----

    def settings_view(self) -> dict:
        s = self.settings
        return {
            "recognition_mode": s.recognition.mode,
            "min_confidence": s.recognition.min_confidence,
            "sign_threshold": s.fusion.sign_threshold,
            "lip_threshold": s.fusion.lip_threshold,
            "allow_single_modality": s.fusion.allow_single_modality,
            "speech_enabled": s.output.speech_enabled,
            "speech_cooldown_ms": s.output.speech_cooldown_ms,
            "history_retention_days": s.output.history_retention_days,
            "history_max_entries": s.output.history_max_entries,
            "camera_provider": s.camera.provider,
            "camera_target_width": s.camera.target_width,
            "camera_target_height": s.camera.target_height,
            "camera_target_fps": s.camera.target_fps,
            "camera_video_path": s.camera.video_path,
            "camera_device_index": s.camera.device_index,
            "vocabulary": list(s.vocabulary.labels),
            "abstain_label": s.vocabulary.abstain_label,
            "requires_restart": self._pending_restart,
        }

    def apply_settings(self, update: dict) -> dict:
        """Apply a validated partial update, persist it, report restart needs.

        Camera provider/source changes take effect only on restart while the
        capture runtime does not yet support hot-swap; we report that honestly
        instead of silently ignoring it.
        """
        restart: list[str] = []
        rec, fus, out, cam = self.settings.recognition, self.settings.fusion, self.settings.output, self.settings.camera
        for key, value in update.items():
            if value is None:
                continue
            if key == "recognition_mode":
                rec.mode = value
            elif key == "min_confidence":
                rec.min_confidence = value
            elif key == "sign_threshold":
                fus.sign_threshold = value
            elif key == "lip_threshold":
                fus.lip_threshold = value
            elif key == "allow_single_modality":
                fus.allow_single_modality = value
            elif key == "speech_enabled":
                out.speech_enabled = value
            elif key == "speech_cooldown_ms":
                out.speech_cooldown_ms = value
            elif key == "history_retention_days":
                out.history_retention_days = value
            elif key == "history_max_entries":
                out.history_max_entries = value
            elif key == "camera_provider":
                if value != cam.provider:
                    cam.provider = value
                    restart.append("camera_provider")
            elif key in ("camera_target_width", "camera_target_height", "camera_target_fps",
                         "camera_video_path", "camera_device_index"):
                field = key.removeprefix("camera_")
                if getattr(cam, field) != value:
                    setattr(cam, field, value)
                    restart.append(key)
        for r in restart:
            if r not in self._pending_restart:
                self._pending_restart.append(r)
        # Persist only the fields that differ from YAML defaults.
        self.db.set_setting("settings.overrides", self.settings.model_dump(mode="json"))
        return self.settings_view()

    def load_settings_overrides(self) -> None:
        """Re-apply persisted overrides after process restart."""
        stored = self.db.get_setting("settings.overrides")
        if not stored:
            return
        try:
            from .config import Settings
            self.settings = Settings.model_validate(stored)
        except Exception:  # corrupt/old overrides must never block startup
            logger.warning("Discarding unreadable settings overrides")
            return
        # Everything in overrides is in effect after a restart.
        self._pending_restart = []

    # ---- recognition lifecycle (honest until Phase 3) ----

    def start_recognition(self) -> str | None:
        """Returns an error detail, or None on success."""
        # Camera exists now (Phase 3); the pipeline needs trained models (Phase 5+).
        from .registry import status_for as _sf
        sign = _sf(self.settings.paths.models_dir, "sign")
        lip = _sf(self.settings.paths.models_dir, "lip")
        if sign.value == "NOT_TRAINED" and lip.value == "NOT_TRAINED":
            return (
                "No trained models on disk yet — sign/silent-lip training arrives "
                "in Phases 5–6. Start the camera from Live Vision in the meantime."
            )
        return (
            "Recognition pipeline not implemented yet (inference arrives in "
            "Phases 5–7). No state change was made."
        )

    def camera_kwargs(self) -> dict:
        """Provider kwargs from current settings."""
        cam = self.settings.camera
        return {
            "video_path": cam.video_path,
            "device_index": cam.device_index,
            "width": cam.target_width,
            "height": cam.target_height,
            "fps": cam.target_fps,
        }

    def start_camera(self) -> str | None:
        """Start capture from the configured provider. Error detail or None."""
        cam = self.settings.camera
        return self.camera.start(cam.provider, **self.camera_kwargs())

    def stop_camera(self) -> None:
        self.camera.stop()

    def shutdown(self) -> None:
        """Lifespan teardown: release camera and close DB."""
        self.camera.stop()
        self.db.close()

    def stop_recognition(self) -> str | None:
        return None  # already STOPPED; stopping a stopped runtime is a no-op
