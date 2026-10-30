"""Face landmark extraction (MediaPipe Tasks, offline model asset).

MediaPipe 1.x quirk: import subpackages by `from ... import Name`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger("silentos.lip")

NUM_LANDMARKS = 478
FACE_MODEL_NAME = "face_landmarker.task"


class LandmarkUnavailable(Exception):
    """MediaPipe or its model asset is missing on this machine."""


class FaceExtractor:
    """Extracts face 478×3 landmarks per frame for lip analysis.

    Construction does no I/O; the first `extract()` builds the task lazily.
    """

    def __init__(self, model_path: str | Path, num_faces: int = 1):
        self._model_path = Path(model_path)
        self._num_faces = num_faces
        self._landmarker = None
        self._timestamp_ms = 0
        self._delegate: str | None = None

    def _ensure(self):
        if self._landmarker is not None:
            return self._landmarker
        if not self._model_path.is_file():
            raise LandmarkUnavailable(
                f"Face face landmark model not found: {self._model_path} — download "
                "face_landmarker.task (see docs/models.md)"
            )
        try:
            from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
            from mediapipe.tasks.python.core.base_options import BaseOptions
        except ImportError as e:
            raise LandmarkUnavailable(f"mediapipe is not importable: {e}") from e
        # CPU (XNNPACK) delegate is killed (SIGKILL) on this host; GPU delegate
        # is the only working path. ponytail: sustained multi-frame GPU loop and
        # Raspberry Pi 4 GPU delegate viability unverified.
        delegate = None
        try:
            delegate = BaseOptions.Delegate.GPU
        except Exception:  # noqa: BLE001
            delegate = None
        last_error: Exception | None = None
        for use_gpu in (True, False):
            if use_gpu and delegate is None:
                continue
            base_opts = BaseOptions(
                model_asset_path=str(self._model_path),
                **({"delegate": delegate} if use_gpu and delegate is not None else {}),
            )
            options = FaceLandmarkerOptions(
                base_options=base_opts,
                running_mode=RunningMode.VIDEO,
                num_faces=self._num_faces,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            try:
                self._landmarker = FaceLandmarker.create_from_options(options)
                self._delegate = "gpu" if use_gpu else "cpu"
                return self._landmarker
            except Exception as e:  # noqa: BLE001
                last_error = e
                self._landmarker = None
        raise LandmarkUnavailable(
            f"Face landmarker failed to initialize: {last_error}"
        ) from last_error

    def extract(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        """Return (478, 3) landmarks for the first detected face, or None."""
        import cv2
        import mediapipe as mp

        landmarker = self._ensure()
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._timestamp_ms += 33
        result = landmarker.detect_for_video(image, self._timestamp_ms)
        if not result.face_landmarks:
            return None
        face = result.face_landmarks[0]
        return np.array([(lm.x, lm.y, lm.z) for lm in face], dtype=np.float64)

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
