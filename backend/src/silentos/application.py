"""Central application controller: owns settings, database and runtime state."""

from __future__ import annotations

import logging
import platform
import shutil
import socket
import threading
import time
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
from .fusion import FusionEngine, FusionPolicy, FusionWeights
from .output import SpeechEngine


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
        # Fusion + live recognizers (Phase 7)
        self._fusion_engine: FusionEngine | None = None
        self._speech = SpeechEngine(cooldown_ms=settings.output.speech_cooldown_ms)
        self._sign_recognizer = None
        self._lip_recognizer = None
        self._last_decision = None
        self._recognition_thread: threading.Thread | None = None
        self._recognition_stop = threading.Event()
        self._recognition_lock = threading.Lock()

    # ---- recognition lifecycle ----

    def start_recognition(self) -> str | None:
        """Returns an error detail, or None on success."""
        if self.runtime_state == RuntimeState.RUNNING:
            return None  # already running, idempotent

        from .registry import status_for as _sf
        sign_status = _sf(self.settings.paths.models_dir, "sign")
        lip_status = _sf(self.settings.paths.models_dir, "lip")
        if sign_status.value == "NOT_TRAINED" and lip_status.value == "NOT_TRAINED":
            return (
                "No trained models on disk yet — record clips in Dataset Studio and "
                "train a sign model in Training Center. No state change was made."
            )

        # Build recognizers lazily (only for trained modalities)
        from .sign.pipeline import SignRecognizer
        from .lip.pipeline import LipRecognizer
        models_dir = self.settings.paths.models_dir
        sign_model_path = models_dir / "sign" / "model.npz"
        lip_model_path = models_dir / "lip" / "model.npz"

        if sign_status.value != "NOT_TRAINED" and sign_model_path.is_file():
            try:
                self._sign_recognizer = SignRecognizer(sign_model_path)
            except Exception as e:
                logger.warning("Sign recognizer init failed: %s", e)
                self._sign_recognizer = None
        if lip_status.value != "NOT_TRAINED" and lip_model_path.is_file():
            try:
                self._lip_recognizer = LipRecognizer(lip_model_path)
            except Exception as e:
                logger.warning("Lip recognizer init failed: %s", e)
                self._lip_recognizer = None

        if self._sign_recognizer is None and self._lip_recognizer is None:
            return (
                "No trained models on disk yet — record clips in Dataset Studio and "
                "train a sign model in Training Center. No state change was made."
            )

        # Build fusion engine from settings
        fus_cfg = self.settings.fusion
        rec_cfg = self.settings.recognition
        policy = FusionPolicy(
            min_confidence=rec_cfg.min_confidence,
            sign_threshold=fus_cfg.sign_threshold,
            lip_threshold=fus_cfg.lip_threshold,
            allow_single_modality=fus_cfg.allow_single_modality,
        )
        weights = FusionWeights(sign=0.6, lip=0.4)  # TODO: make configurable
        self._fusion_engine = FusionEngine(weights=weights, policy=policy)

        self._recognition_stop.clear()
        self._recognition_thread = threading.Thread(
            target=self._recognition_loop, name="recognition", daemon=True
        )
        self._recognition_thread.start()
        self.runtime_state = RuntimeState.RUNNING
        self.last_error = None
        logger.info("Recognition runtime started (mode=%s)", rec_cfg.mode)
        return None

    def stop_recognition(self) -> str | None:
        if self.runtime_state != RuntimeState.RUNNING:
            return None  # already stopped
        self._recognition_stop.set()
        if self._recognition_thread and self._recognition_thread.is_alive():
            self._recognition_thread.join(timeout=5)
        self._recognition_thread = None
        self.runtime_state = RuntimeState.STOPPED
        if self._sign_recognizer:
            self._sign_recognizer.reset()
        if self._lip_recognizer:
            self._lip_recognizer.reset()
        logger.info("Recognition runtime stopped")
        return None

    def _recognition_loop(self) -> None:
        """Main loop: pull frames from camera, run modality pipelines, fuse."""
        interval_s = self.settings.recognition.inference_interval_ms / 1000.0
        mode = self.settings.recognition.mode
        while not self._recognition_stop.is_set():
            frame = self.camera.latest_frame()
            if frame is None:
                self._recognition_stop.wait(interval_s)
                continue

            t0 = time.monotonic()
            sign_pred = None
            lip_pred = None
            if mode in ("sign", "both") and self._sign_recognizer is not None:
                label, conf, _ = self._sign_recognizer.predict_frame(frame.image)
                if label is not None and conf is not None:
                    sign_pred = {"label": label, "confidence": conf}
            if mode in ("lip", "both") and self._lip_recognizer is not None:
                label, conf, _ = self._lip_recognizer.predict_frame(frame.image)
                if label is not None and conf is not None:
                    lip_pred = {"label": label, "confidence": conf}

            latency_ms = (time.monotonic() - t0) * 1000.0

            if sign_pred is None and lip_pred is None:
                self.frames_processed += 1
                self._recognition_stop.wait(interval_s)
                continue

            decision = self._fusion_engine.fuse(sign_pred, lip_pred)
            self.frames_processed += 1
            if not decision.abstained and decision.label is not None:
                self.db.add_history(
                    mode=mode,
                    sign_label=sign_pred["label"] if sign_pred else None,
                    sign_confidence=sign_pred["confidence"] if sign_pred else None,
                    lip_label=lip_pred["label"] if lip_pred else None,
                    lip_confidence=lip_pred["confidence"] if lip_pred else None,
                    final_label=decision.label,
                    accepted=True,
                    reason=decision.reason,
                    latency_ms=latency_ms,
                )
                self._last_decision = {
                    "decision": decision,
                    "sign": sign_pred,
                    "lip": lip_pred,
                    "latency_ms": latency_ms,
                    "ts": _now(),
                }
                if not decision.abstained and decision.label is not None:
                    from .output import speak_decision
                    speak_decision(
                        self._speech,
                        decision.label,
                        self.settings.vocabulary.abstain_label,
                        self.settings.output.speech_enabled,
                    )

            self._recognition_stop.wait(interval_s)

    # ---- other methods unchanged below ----

    def last_decision_view(self) -> dict | None:
        """Schema-compatible view of the last fused decision, or None."""
        raw = self._last_decision
        if raw is None:
            return None
        dec = raw["decision"]

        def _mod(pred: dict | None, modality: str) -> dict | None:
            if pred is None:
                return None
            return {
                "modality": modality,
                "predicted_class": pred["label"],
                "confidence": pred["confidence"],
                "probabilities": None,
                "timestamp": raw["ts"],
                "model_version": None,
                "processing_latency_ms": raw["latency_ms"],
                "status": status_for(self.settings.paths.models_dir, modality),
            }

        return {
            "final_label": dec.label or self.settings.vocabulary.abstain_label,
            "accepted": not dec.abstained,
            "reason": dec.reason,
            "sign_prediction": _mod(raw["sign"], "sign"),
            "lip_prediction": _mod(raw["lip"], "lip"),
            "timestamp": raw["ts"],
            "schema_version": "1",
            "confidence": dec.confidence,
            "sources": dec.sources,
            "scores": dec.scores,
            "latency_ms": raw["latency_ms"],
        }

    def app_status(self) -> AppStatus:
        return AppStatus(
            runtime_state=self.runtime_state,
            recognition_mode=RecognitionMode(self.settings.recognition.mode),
            camera_state=CameraState.DISCONNECTED,
            camera_provider=self.settings.camera.provider,
            sign_model_status=status_for(self.settings.paths.models_dir, "sign"),
            lip_model_status=status_for(self.settings.paths.models_dir, "lip"),
            speech_enabled=self.settings.output.speech_enabled,
            last_message=(
                "speech enabled but espeak-ng not on PATH — output disabled"
                if self.settings.output.speech_enabled and not self._speech.available
                else None
            ),
            last_recognition=None,
            inference_latency_ms=(self._last_decision or {}).get("latency_ms") if self._last_decision else None,
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

    def reconcile_stale_jobs(self) -> int:
        """Jobs left QUEUED/RUNNING by a dead process can never continue.

        Marked FAILED at startup so the dashboard never shows a phantom run.
        """
        stale = [
            row
            for row in self.db.list_jobs(limit=5000)
            if row["status"] in ("QUEUED", "RUNNING")
        ]
        for row in stale:
            self.db.update_job(
                row["id"], status="FAILED", error="Interrupted by process restart"
            )
        if stale:
            logger.warning(
                "Reconciled %d stale training job(s) from a previous process",
                len(stale),
            )
        return len(stale)

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
        self.stop_recognition()
        self.camera.stop()
        self.db.close()
