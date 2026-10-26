"""Concrete camera providers.

- MockCameraProvider       deterministic frames, tests only
- VideoFileProvider        replay a clip from disk (loops)
- DevelopmentWebcamProvider laptop/USB webcam via V4L2 (cv2)
- PiCameraProvider         Raspberry Pi Camera Module (Picamera2, guarded)
- PiUsbWebcamProvider      USB webcam on the Pi (V4L2 via cv2)

Pi providers raise CameraUnavailable on non-Pi machines instead of pretending.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import numpy as np

from .base import CameraError, CameraProvider, CameraSpec, CameraUnavailable


class MockCameraProvider(CameraProvider):
    """Solid-color frames with a burned-in counter. No hardware, no I/O."""

    name = "mock"

    def __init__(self, width: int = 640, height: int = 480, fps: float = 30.0):
        self._width = width
        self._height = height
        self._fps = fps
        self._open = False
        self._n = 0

    def open(self) -> CameraSpec:
        self._open = True
        self._n = 0
        return CameraSpec(self._width, self._height, self._fps, label="Mock source")

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._open:
            return False, None
        self._n += 1
        frame = np.full((self._height, self._width, 3), (40, 40, 40), dtype=np.uint8)
        cv2.putText(
            frame, f"MOCK {self._n}", (24, 48),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 255), 2, cv2.LINE_AA,
        )
        return True, frame

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open


class VideoFileProvider(CameraProvider):
    """Replays a video file, looping at EOF."""

    name = "video_file"

    def __init__(self, path: str, width: int = 0, height: int = 0, fps: float = 0.0):
        self._path = path
        self._req_w, self._req_h, self._req_fps = width, height, fps
        self._cap: cv2.VideoCapture | None = None
        self._spec: CameraSpec | None = None

    def open(self) -> CameraSpec:
        if not self._path or not Path(self._path).is_file():
            raise CameraUnavailable(f"Video file not found: {self._path or '(not configured)'}")
        cap = cv2.VideoCapture(self._path)
        if not cap.isOpened():
            raise CameraError(f"Could not open video file: {self._path}")
        self._cap = cap
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self._spec = CameraSpec(w, h, fps, label=f"Video file {Path(self._path).name}",
                                device_path=self._path)
        return self._spec

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        if not ok:  # EOF or decode error -> loop
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok:
                return False, None
        return True, frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None


class _Cv2CaptureProvider(CameraProvider):
    """Shared V4L2 webcam implementation (development + Pi USB webcam)."""

    name = "cv2_webcam"

    def __init__(self, device: int | str, width: int = 640, height: int = 480, fps: float = 30.0):
        self._device = device
        self._req_w, self._req_h, self._req_fps = width, height, fps
        self._cap: cv2.VideoCapture | None = None
        self._spec: CameraSpec | None = None

    def open(self) -> CameraSpec:
        cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise CameraUnavailable(
                f"Cannot open video device {self._device!r} (V4L2 open failed)"
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._req_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._req_h)
        cap.set(cv2.CAP_PROP_FPS, self._req_fps)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or self._req_fps
        if w <= 0 or h <= 0:
            cap.release()
            raise CameraError(f"Device {self._device!r} opened but reported no frame size")
        self._cap = cap
        path = f"/dev/video{self._device}" if isinstance(self._device, int) else str(self._device)
        self._spec = CameraSpec(w, h, fps, label="Webcam", device_path=path)
        return self._spec

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        if not ok:
            return False, None
        return True, frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None


class DevelopmentWebcamProvider(_Cv2CaptureProvider):
    name = "development_webcam"

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: float = 30.0):
        super().__init__(device_index, width, height, fps)


class PiUsbWebcamProvider(_Cv2CaptureProvider):
    name = "pi_usb_webcam"

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: float = 30.0):
        super().__init__(device_index, width, height, fps)


def _is_raspberry_pi() -> bool:
    try:
        return "raspberry" in Path("/proc/device-tree/model").read_text().lower()
    except OSError:
        return False


class PiCameraProvider(CameraProvider):
    """Raspberry Pi Camera Module via Picamera2 (guarded import)."""

    name = "pi_camera"
    always_available = False

    def __init__(self, width: int = 640, height: int = 480, fps: float = 30.0):
        self._w, self._h, self._fps = width, height, fps
        self._picam = None

    def open(self) -> CameraSpec:
        if not _is_raspberry_pi():
            raise CameraUnavailable(
                "Not running on a Raspberry Pi — pi_camera is unavailable on this host"
            )
        try:
            from picamera2 import Picamera2  # type: ignore[import-not-found]
        except ImportError as e:
            raise CameraUnavailable(
                "picamera2 is not installed (install python3-picamera2 on the Pi)"
            ) from e
        try:
            self._picam = Picamera2()
            config = self._picam.create_video_configuration(
                main={"size": (self._w, self._h), "format": "RGB888"}
            )
            self._picam.configure(config)
            self._picam.start()
        except Exception as e:
            self._picam = None
            raise CameraError(f"Picamera2 failed to start: {e}") from e
        return CameraSpec(self._w, self._h, self._fps, label="Pi Camera Module",
                          device_path="picamera2")

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._picam is None:
            return False, None
        frame = self._picam.capture_array()  # RGB
        if frame is None:
            return False, None
        return True, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def close(self) -> None:
        if self._picam is not None:
            try:
                self._picam.stop()
                self._picam.close()
            finally:
                self._picam = None

    @property
    def is_open(self) -> bool:
        return self._picam is not None


PROVIDERS: dict[str, type[CameraProvider]] = {
    MockCameraProvider.name: MockCameraProvider,
    VideoFileProvider.name: VideoFileProvider,
    DevelopmentWebcamProvider.name: DevelopmentWebcamProvider,
    PiCameraProvider.name: PiCameraProvider,
    PiUsbWebcamProvider.name: PiUsbWebcamProvider,
}


def build_provider(
    name: str,
    *,
    video_path: str | None = None,
    device_index: int = 0,
    width: int = 640,
    height: int = 480,
    fps: float = 30.0,
) -> CameraProvider:
    """Instantiate a provider by registry name (never touches hardware)."""
    if name not in PROVIDERS:
        raise CameraUnavailable(f"Unknown camera provider: {name}")
    cls = PROVIDERS[name]
    if cls is VideoFileProvider:
        return VideoFileProvider(video_path or "", width, height, fps)
    if cls in (DevelopmentWebcamProvider, PiUsbWebcamProvider):
        return cls(device_index, width, height, fps)  # type: ignore[call-arg]
    return cls(width, height, fps)  # type: ignore[call-arg]


def discover_v4l2() -> list[tuple[str, str]]:
    """[(device_path, name)] from sysfs — real devices only."""
    sys_video = Path("/sys/class/video4linux")
    if not sys_video.is_dir():
        return []
    out = []
    for entry in sorted(sys_video.iterdir()):
        name_file = entry / "name"
        label = name_file.read_text().strip() if name_file.exists() else entry.name
        out.append((f"/dev/{entry.name}", label))
    return out
