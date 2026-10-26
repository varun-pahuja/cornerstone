"""Camera subsystem: providers, manager, discovery."""

from .base import CameraError, CameraProvider, CameraSpec, CameraUnavailable
from .manager import CameraManager, FramePacket
from .providers import PROVIDERS, build_provider, discover_v4l2

__all__ = [
    "CameraError",
    "CameraProvider",
    "CameraSpec",
    "CameraUnavailable",
    "CameraManager",
    "FramePacket",
    "PROVIDERS",
    "build_provider",
    "discover_v4l2",
]
