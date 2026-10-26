"""CameraManager: one capture thread, one bounded latest-frame buffer.

The buffer is a `deque(maxlen=1)` — a bounded queue that drops stale frames:
live recognition and preview only ever need the freshest frame, so older ones
are discarded the moment a new one arrives. `frames_dropped` counts them.

Locking: `_life` serializes start/stop (lifecycle), `_lock` guards state and
the frame buffer. The capture loop only ever takes `_lock`, so joining a
thread never happens while holding it.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from .base import CameraError, CameraProvider, CameraUnavailable
from .providers import build_provider

logger = logging.getLogger("silentos.camera")


@dataclass
class FramePacket:
    seq: int
    captured_at: float  # time.monotonic()
    frame: Any  # np.ndarray; kept untyped so numpy stays optional at import time


class CameraManager:
    """Thread-safe camera lifecycle: open -> capture loop -> close."""

    def __init__(self) -> None:
        self._life = threading.Lock()
        self._lock = threading.Lock()
        self._provider: CameraProvider | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._frames: deque[FramePacket] = deque(maxlen=1)
        self._state = "DISCONNECTED"
        self._error: str | None = None
        self._spec: dict[str, Any] = {}
        self._frames_captured = 0
        self._frames_dropped = 0
        self._last_frame_monotonic: float | None = None
        self._provider_name = ""

    # ---- lifecycle ----

    def start(self, provider_name: str, **provider_kwargs: Any) -> str | None:
        """Open the provider and start capturing. Returns an error detail or None."""
        with self._life:
            with self._lock:
                already = self._state == "CONNECTED" and self._provider_name == provider_name
            if already:
                return None
            self._teardown()

            with self._lock:
                self._state = "CONNECTING"
                self._error = None
                self._provider_name = provider_name

            try:
                provider = build_provider(provider_name, **provider_kwargs)
                spec = provider.open()
            except CameraUnavailable as e:
                with self._lock:
                    self._state = "UNAVAILABLE"
                    self._error = str(e)
                logger.warning("Camera unavailable (%s): %s", provider_name, e)
                return str(e)
            except Exception as e:  # noqa: BLE001 — any open failure must surface honestly
                with self._lock:
                    self._state = "ERROR"
                    self._error = str(e)
                logger.error("Camera open failed (%s): %s", provider_name, e)
                return str(e)

            with self._lock:
                self._provider = provider
                self._spec = {
                    "width": spec.width,
                    "height": spec.height,
                    "fps": spec.fps,
                    "label": spec.label,
                    "device_path": spec.device_path,
                }
                self._frames.clear()
                self._frames_captured = 0
                self._frames_dropped = 0
                self._last_frame_monotonic = None
                self._state = "CONNECTED"
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._capture_loop, name="camera-capture", daemon=True
                )
                self._thread.start()
            logger.info(
                "Camera started: %s (%sx%s @ %sfps)",
                provider_name, spec.width, spec.height, spec.fps,
            )
            return None

    def stop(self) -> None:
        with self._life:
            self._teardown()

    def _teardown(self) -> None:
        """Stop capture and release the device. Caller holds `_life`."""
        with self._lock:
            thread = self._thread
            provider = self._provider
            self._thread = None
            self._provider = None
            self._state = "DISCONNECTED"
            self._spec = {}
            self._stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        if provider is not None:
            try:
                provider.close()
            except Exception:  # noqa: BLE001 — close must never raise out of stop
                logger.exception("Camera close failed")

    # ---- capture loop ----

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                provider = self._provider
                fps = float(self._spec.get("fps") or 30.0)
            if provider is None:
                return
            t0 = time.monotonic()
            try:
                ok, frame = provider.read()
            except Exception as e:  # noqa: BLE001 — device vanished mid-read
                with self._lock:
                    self._state = "ERROR"
                    self._error = f"Frame read failed: {e}"
                logger.error("Camera read error: %s", e)
                return
            if not ok or frame is None:
                with self._lock:
                    self._state = "ERROR"
                    self._error = "Frame read failed (device returned no frame)"
                logger.error("Camera read failed: no frame")
                return
            with self._lock:
                if self._frames:
                    self._frames_dropped += 1  # bounded deque evicts the stale packet
                self._frames.append(
                    FramePacket(
                        seq=self._frames_captured,
                        captured_at=time.monotonic(),
                        frame=frame,
                    )
                )
                self._frames_captured += 1
                self._last_frame_monotonic = time.monotonic()
            # Throttle non-blocking sources (mock/file) to the configured fps.
            elapsed = time.monotonic() - t0
            delay = (1.0 / fps) - elapsed if fps > 0 else 0.0
            if delay > 0:
                self._stop.wait(delay)

    # ---- reads ----

    def latest_frame(self) -> FramePacket | None:
        with self._lock:
            return self._frames[-1] if self._frames else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            age_ms = None
            if self._last_frame_monotonic is not None:
                age_ms = round((time.monotonic() - self._last_frame_monotonic) * 1000, 1)
            return {
                "state": self._state,
                "provider": self._provider_name or None,
                "width": self._spec.get("width"),
                "height": self._spec.get("height"),
                "fps": self._spec.get("fps"),
                "frames_captured": self._frames_captured,
                "frames_dropped": self._frames_dropped,
                "last_frame_age_ms": age_ms,
                "error": self._error,
            }

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._state == "CONNECTED" and self._thread is not None
