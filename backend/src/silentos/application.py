"""Central application controller: owns settings, database and runtime state."""

from __future__ import annotations

import platform
import shutil
import socket
from datetime import datetime, timezone

import psutil

from .config import Settings
from .database import Database
from .schemas import (
    AppStatus,
    CameraState,
    ModelStatus,
    RecognitionMode,
    RuntimeState,
    SystemMetrics,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Application:
    """Holds real runtime state. No fabricated values: unavailable metrics stay None."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.paths.ensure()
        self.db = Database(settings.paths.data_dir / "silentos.db")
        self.runtime_state = RuntimeState.STOPPED
        self.last_error: str | None = None
        self.frames_processed = 0
        # Prime the CPU counter so the first reported value is a real measurement
        # over the process lifetime, not a fabricated zero.
        psutil.cpu_percent(interval=None)

    def app_status(self) -> AppStatus:
        return AppStatus(
            runtime_state=self.runtime_state,
            recognition_mode=RecognitionMode(self.settings.recognition.mode),
            camera_state=CameraState.DISCONNECTED,
            camera_provider=self.settings.camera.provider,
            sign_model_status=ModelStatus.NOT_LOADED,
            lip_model_status=ModelStatus.NOT_LOADED,
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
