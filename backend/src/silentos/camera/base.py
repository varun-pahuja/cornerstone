"""Camera provider interface.

Every provider is a blocking `read()` source of BGR frames. Providers must be
import-safe on machines without their hardware: construction never touches
hardware, `open()` raises `CameraUnavailable` when the hardware/dependency is
missing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


class CameraError(Exception):
    """Camera failed at runtime (I/O error, device vanished)."""


class CameraUnavailable(Exception):
    """Provider cannot run on this machine (missing hardware/library)."""


@dataclass
class CameraSpec:
    """What a provider reports after a successful open()."""

    width: int
    height: int
    fps: float
    label: str = ""
    device_path: str | None = None
    extra: dict = field(default_factory=dict)


class CameraProvider(ABC):
    """Common interface for all camera sources."""

    #: registry key, matches settings.camera.provider
    name: str = "base"
    #: False when the machine lacks the hardware/library for this provider
    always_available: bool = True

    @abstractmethod
    def open(self) -> CameraSpec:
        """Acquire the device. Raises CameraUnavailable/CameraError."""

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None]:
        """Return (ok, BGR frame). ok=False means fatal read failure."""

    @abstractmethod
    def close(self) -> None:
        """Release the device. Must be idempotent."""

    @property
    @abstractmethod
    def is_open(self) -> bool: ...
