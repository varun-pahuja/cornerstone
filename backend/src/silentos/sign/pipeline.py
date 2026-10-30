"""Buffered sign recognition: frames in -> (label, confidence) out, or abstain."""

from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

import numpy as np

from .features import MIN_FRAMES, sequence_to_features
from .landmarks import HAND_MODEL_NAME, HandExtractor
from .model import LogisticBaseline

logger = logging.getLogger("silentos.sign")

BUFFER_LEN = 96  # keep ~3 s of detections at stride 2 / 30 fps
CONFIDENCE_FLOOR = 0.45  # below this the pipeline abstains with PLEASE REPEAT


class SignRecognizer:
    """Holds a short landmark history and the loaded baseline.

    `predict_frame` runs continuously on each annotated frame; classification
    only happens once the buffer has enough detections (MIN_FRAMES).
    """

    def __init__(
        self,
        model_path: str | Path,
        extractor: HandExtractor | None = None,
        confidence_floor: float = CONFIDENCE_FLOOR,
    ):
        self._model_path = Path(model_path)
        self._model: LogisticBaseline | None = None
        # Default to the landmark extractor next to the model (models/assets/).
        # HandExtractor construction does no I/O, so a missing asset still
        # surfaces at the first frame with a clear error instead of silently
        # abstaining forever.
        self._extractor = extractor or HandExtractor(
            self._model_path.parent.parent / "assets" / HAND_MODEL_NAME
        )
        self._floor = confidence_floor
        self._buffer: deque[np.ndarray] = deque(maxlen=BUFFER_LEN)
        self._model_version: str | None = None
        if self._model_path.is_file():
            self.reload()

    # ---- model lifecycle ----

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def version(self) -> str | None:
        return self._model_version

    @property
    def labels(self) -> list[str]:
        return self._model.classes if self._model else []

    def reload(self) -> bool:
        """(Re)load model.npz if present. False = not trained yet."""
        if not self._model_path.is_file():
            self._model = None
            self._model_version = None
            return False
        self._model = LogisticBaseline.load(self._model_path)
        manifest = self._model_path.parent / "manifest.json"
        if manifest.is_file():
            import json

            try:
                self._model_version = json.loads(manifest.read_text()).get("version")
            except (OSError, ValueError):
                self._model_version = None
        logger.info("Sign model loaded: version=%s labels=%s", self._model_version, self.labels)
        return True

    def unload(self) -> None:
        self._model = None
        self._model_version = None

    # ---- recognition ----

    def predict_frame(
        self, frame_bgr: np.ndarray
    ) -> tuple[str | None, float | None, np.ndarray | None]:
        """Consume one frame.

        Returns (label, confidence, landmarks):
        - label is None when the model is absent, no hand, or too few frames
          seen yet (recognition engine keeps showing "model not ready" honestly).
        - confidence < floor -> label becomes the abstain string handled by the
          caller (kept raw here so tests can check calibration thresholds).
        """
        if self._extractor is None or self._model is None:
            return None, None, None
        landmarks = self._extractor.extract(frame_bgr)
        if landmarks is None:
            return None, None, None
        self._buffer.append(landmarks)
        if len(self._buffer) < MIN_FRAMES:
            return None, None, landmarks
        seq = np.stack(self._buffer)
        features = sequence_to_features(seq).reshape(1, -1)
        label, confidence = self._model.predict(features)[0]
        return label, confidence, landmarks

    def reset(self) -> None:
        self._buffer.clear()

    def close(self) -> None:
        if self._extractor is not None:
            self._extractor.close()
        self._buffer.clear()
