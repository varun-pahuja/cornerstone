"""Sign feature pipeline: landmark sequence -> fixed-length feature vector.

Deterministic pure numpy. Two invariants (tested):
- scale invariant  (a hand 2x farther from the camera maps to the same vector)
- translation invariant (moving the hand across the frame changes nothing)
"""

from __future__ import annotations

import numpy as np

SEQ_LEN = 32          # temporal resample target
NUM_LANDMARKS = 21
NUM_COORDS = 3
FEATURE_DIM = SEQ_LEN * NUM_LANDMARKS * NUM_COORDS  # 2016
MIN_FRAMES = 8        # too few detections to form a real sequence


def normalize_landmarks(seq: np.ndarray) -> np.ndarray:
    """(T, 21, 3) -> wrist-relative, per-frame scale-normalized.

    Wrist (landmark 0) becomes the origin each frame; the max distance from
    the wrist becomes 1.0. Pure translation/scale removal — no fitting, no
    randomness.
    """
    seq = np.asarray(seq, dtype=np.float64)
    if seq.ndim != 3 or seq.shape[1] != NUM_LANDMARKS:
        raise ValueError(f"expected (T, {NUM_LANDMARKS}, 3), got {seq.shape}")
    rel = seq - seq[:, :1, :]
    scale = np.linalg.norm(rel, axis=2).max(axis=1, keepdims=True)  # (T, 1)
    scale = np.where(scale < 1e-9, 1.0, scale)
    return rel / scale[:, :, None]


def resample(seq: np.ndarray, length: int = SEQ_LEN) -> np.ndarray:
    """Linear time resampling of a (T, 21, 3) sequence to exactly `length` frames."""
    seq = np.asarray(seq, dtype=np.float64)
    t = seq.shape[0]
    if t == length:
        return seq.copy()
    if t < 1:
        raise ValueError("empty sequence")
    x_old = np.linspace(0.0, 1.0, t)
    x_new = np.linspace(0.0, 1.0, length)
    flat = seq.reshape(t, -1)
    out = np.empty((length, flat.shape[1]), dtype=np.float64)
    for col in range(flat.shape[1]):
        out[:, col] = np.interp(x_new, x_old, flat[:, col])
    return out.reshape((length, *seq.shape[1:]))


def sequence_to_features(seq: np.ndarray) -> np.ndarray:
    """Raw landmark sequence (T>=MIN_FRAMES, 21, 3) -> flat feature vector (2016,)."""
    seq = np.asarray(seq, dtype=np.float64)
    if seq.shape[0] < MIN_FRAMES:
        raise ValueError(f"need at least {MIN_FRAMES} landmark frames, got {seq.shape[0]}")
    normalized = normalize_landmarks(seq)
    fixed = resample(normalized, SEQ_LEN)
    return fixed.reshape(FEATURE_DIM)
