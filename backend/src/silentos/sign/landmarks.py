"""Hand landmark extraction (MediaPipe Tasks, offline model asset).

MediaPipe 1.x quirk: `mediapipe/__init__.py` rebinds `mediapipe.tasks` to the
`python` subpackage, so `import mediapipe.tasks.python.vision as v` fails at
the attribute-binding step. Plain `from … import Name` works (it resolves
through sys.modules) — that is the import style used here.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

logger = logging.getLogger("silentos.sign")

NUM_LANDMARKS = 21
HAND_MODEL_NAME = "hand_landmarker.task"

# GPU first by default: the CPU delegate is killed (SIGKILL) on the dev host.
# Colab/headless hosts have no EGL, and the GPU delegate aborts the whole
# process inside create_from_options() — a C++ LOG(FATAL) Python cannot catch,
# so the CPU-only path must be selectable. Set SILENTOS_MEDIAPIPE_DELEGATE=cpu.
DELEGATE_ENV = "SILENTOS_MEDIAPIPE_DELEGATE"


def delegate_order() -> tuple[str, ...]:
    if os.environ.get(DELEGATE_ENV, "").strip().lower() == "cpu":
        return ("cpu",)
    return ("gpu", "cpu")


class LandmarkUnavailable(Exception):
    """MediaPipe or its model asset is missing on this machine."""


class HandExtractor:
    """Extracts one hand's 21×3 landmarks per frame.

    Construction does no I/O; the first `extract()` builds the task (lazy), so
    a missing asset surfaces at the honest moment with a clear message.
    """

    def __init__(self, model_path: str | Path, num_hands: int = 1):
        self._model_path = Path(model_path)
        self._num_hands = num_hands
        self._landmarker = None
        self._timestamp_ms = 0
        self._delegate: str | None = None

    def _ensure(self):
        if self._landmarker is not None:
            return self._landmarker
        if not self._model_path.is_file():
            raise LandmarkUnavailable(
                f"Hand landmark model not found: {self._model_path} — download "
                "hand_landmarker.task (see docs/models.md)"
            )
        try:
            from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode
            from mediapipe.tasks.python.core.base_options import BaseOptions
        except ImportError as e:
            raise LandmarkUnavailable(
                f"mediapipe is not importable: {e}"
            ) from e
        # ponytail: GPU delegate unproven for sustained multi-frame loops on
        # the dev host and unverified on Raspberry Pi 4 target.
        last_error: Exception | None = None
        for name in delegate_order():
            base_opts = BaseOptions(model_asset_path=str(self._model_path))
            if name == "gpu":
                try:
                    base_opts = BaseOptions(
                        model_asset_path=str(self._model_path),
                        delegate=BaseOptions.Delegate.GPU,
                    )
                except Exception:  # noqa: BLE001
                    continue
            options = HandLandmarkerOptions(
                base_options=base_opts,
                running_mode=RunningMode.VIDEO,
                num_hands=self._num_hands,
                min_hand_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            try:
                self._landmarker = HandLandmarker.create_from_options(options)
                self._delegate = name
                return self._landmarker
            except Exception as e:  # noqa: BLE001
                last_error = e
                self._landmarker = None
        raise LandmarkUnavailable(
            f"Hand landmarker failed to initialize: {last_error}"
        ) from last_error

    def extract(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        """Return (21, 3) landmarks for the first detected hand, or None."""
        import cv2
        import mediapipe as mp

        landmarker = self._ensure()
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # VIDEO mode requires strictly increasing timestamps.
        self._timestamp_ms += 33
        result = landmarker.detect_for_video(image, self._timestamp_ms)
        if not result.hand_landmarks:
            return None
        hand = result.hand_landmarks[0]
        return np.array([(lm.x, lm.y, lm.z) for lm in hand], dtype=np.float64)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
