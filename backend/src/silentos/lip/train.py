"""Sign model training: dataset -> landmarks -> baseline -> evaluation -> export.

Honest reporting: only metrics actually computed are returned (no val accuracy
when there is no val split, no score at all when there is not enough data —
an explicit error instead).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from ..dataset import load_manifest, manifest_path
from .features import MIN_FRAMES, sequence_to_features
from .landmarks import FaceExtractor

logger = logging.getLogger("silentos.lip")

PREPROCESSING_VERSION = "sign_v1"
MIN_TRAIN_CLIPS = 4
MIN_CLASSES = 2


class TrainingError(Exception):
    """Training cannot proceed — reason is user-facing and honest."""


def _decode_landmark_sequence(
    clip_path: Path, extractor: Any, max_frames: int = 120
) -> np.ndarray | None:
    """Decode a clip and collect landmark frames. None when detection is too sparse."""
    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        return None
    frames: list[np.ndarray] = []
    read = 0
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        read += 1
        if read % 2:  # temporal stride 2 — halve work, keep motion
            continue
        landmarks = extractor.extract(frame)
        if landmarks is not None:
            frames.append(landmarks)
    cap.release()
    if len(frames) < MIN_FRAMES:
        return None
    return np.stack(frames)


def _macro_f1(confusion: np.ndarray) -> float:
    f1s = []
    for i in range(confusion.shape[0]):
        tp = confusion[i, i]
        fp = confusion[:, i].sum() - tp
        fn = confusion[i, :].sum() - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def _evaluate(model, X: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    preds = model.predict(X)
    y_hat = np.array([p for p, _ in preds])
    conf = np.zeros((len(model.classes), len(model.classes)), dtype=int)
    idx = {c: i for i, c in enumerate(model.classes)}
    correct = 0
    for truth, hat in zip(y, y_hat, strict=True):
        conf[idx[truth], idx[hat]] += 1
        correct += truth == hat
    return {
        "accuracy": round(correct / len(y), 4),
        "macro_f1": round(_macro_f1(conf), 4),
        "support": int(len(y)),
        "confusion_matrix": conf.tolist(),
    }


def validate_request(settings, dataset_id: str) -> tuple[list, dict]:
    """Shared precheck for the training route (fail fast, no phantom job)
    and train_sign itself. Raises TrainingError with a user-facing reason.

    Returns (train_clips, eval_by_split) for sign modality.
    """
    mp = manifest_path(settings.paths.manifests_dir, dataset_id)
    if not mp.is_file():
        raise TrainingError(
            f"Dataset '{dataset_id}' does not exist — record or import clips first"
        )
    manifest = load_manifest(mp)
    if not manifest.splits:
        raise TrainingError(
            "No splits for this dataset — generate participant-based splits in "
            "Dataset Studio before training"
        )

    participants: dict[str, str] = manifest.splits.get("participants", {})
    train_clips = [
        c for c in manifest.clips
        if c.modality == "lip" and participants.get(c.participant_id) == "train"
    ]
    eval_by_split = {
        split: [
            c for c in manifest.clips
            if c.modality == "lip" and participants.get(c.participant_id) == split
        ]
        for split in ("val", "test")
    }

    if len(train_clips) < MIN_TRAIN_CLIPS:
        raise TrainingError(
            f"Only {len(train_clips)} sign clip(s) in the train split — "
            f"need at least {MIN_TRAIN_CLIPS} to train honestly"
        )
    classes = sorted({c.label for c in train_clips})
    if len(classes) < MIN_CLASSES:
        raise TrainingError(
            f"Train split has {len(classes)} class(es) ({classes}) — need at least "
            f"{MIN_CLASSES} vocabulary classes with sign clips"
        )
    return train_clips, eval_by_split


def train_lip(
    *,
    settings,
    dataset_id: str = "default",
    seed: int = 42,
    epochs: int = 40,
    lr: float = 0.5,
    l2: float = 1e-3,
    extractor: Any | None = None,
    progress_cb: Callable[[int, int, float], None] | None = None,
) -> dict[str, Any]:
    """Train the sign baseline and export model.npz + model.onnx + manifest.json.

    `extractor` is injectable for tests; production passes the real
    FaceExtractor (or None -> built from the settings asset path).
    """
    from .model import LogisticBaseline

    paths = settings.paths
    train_clips, eval_by_split = validate_request(settings, dataset_id)

    if extractor is None:
        extractor = FaceExtractor(paths.assets_dir / "face_landmarker.task")

    # 1. feature extraction (real decode + real or injected landmarks)
    X_train, y_train, skipped = [], [], []
    for clip in train_clips:
        seq = _decode_landmark_sequence(paths.data_dir / clip.file, extractor)
        if seq is None:
            skipped.append(clip.file)
            continue
        X_train.append(sequence_to_features(seq))
        y_train.append(clip.label)
    if len(X_train) < MIN_TRAIN_CLIPS - len(skipped) or len(X_train) < 2:
        raise TrainingError(
            f"Only {len(X_train)} usable train clip(s) after landmark extraction "
            f"({len(skipped)} skipped: hand not detected enough frames). "
            "Check lighting/framing or record again."
        )
    if len(set(y_train)) < MIN_CLASSES:
        raise TrainingError(
            f"Usable train clips cover {sorted(set(y_train))} — need >=2 classes after skipping"
        )

    def load_split(clips):
        X, y, sk = [], [], []
        for clip in clips:
            seq = _decode_landmark_sequence(paths.data_dir / clip.file, extractor)
            if seq is None:
                sk.append(clip.file)
                continue
            X.append(sequence_to_features(seq))
            y.append(clip.label)
        return np.array(X), np.array(y), sk

    # 2. train
    model = LogisticBaseline(lr=lr, epochs=epochs, l2=l2, seed=seed)
    losses = model.fit(np.array(X_train), np.array(y_train), progress_cb=progress_cb)

    # 3. evaluation — only on splits that actually contain sign clips
    evaluation: dict[str, Any] = {
        "train": _evaluate(model, np.array(X_train), np.array(y_train)),
        "clips_used": len(X_train),
        "clips_skipped": skipped,
        "classes": model.classes,
        "final_loss": round(losses[-1], 6) if losses else None,
    }
    for split, clips in eval_by_split.items():
        if not clips:
            evaluation[split] = None  # honestly absent, not a fake zero
            continue
        X_e, y_e, sk_e = load_split(clips)
        if len(X_e) == 0:
            evaluation[split] = {"note": f"no usable {split} clips", "skipped": sk_e}
            continue
        evaluation[split] = _evaluate(model, X_e, y_e)
        evaluation[split]["clips_skipped"] = sk_e

    # 4. export artifacts
    out_dir = paths.models_dir / "lip"
    out_dir.mkdir(parents=True, exist_ok=True)
    npz_path = out_dir / "model.npz"
    onnx_path = out_dir / "model.onnx"
    model.save(npz_path)
    model.export_onnx(onnx_path)

    version = hashlib.sha256(npz_path.read_bytes()).hexdigest()[:12]
    trained_at = datetime.now(timezone.utc).isoformat()
    try:
        import mediapipe
        mp_ver = mediapipe.__version__
    except Exception:  # noqa: BLE001
        mp_ver = "unknown"

    manifest_out = {
        "model_id": "lip",
        "version": version,
        "modality": "lip",
        "labels": model.classes,
        "trained_at": trained_at,
        "dataset_id": dataset_id,
        "seed": seed,
        "hyperparameters": {"lr": lr, "epochs": epochs, "l2": l2, "seed": seed},
        "input_shape": [1, 2016],
        "preprocessing_version": PREPROCESSING_VERSION,
        "feature": {"seq_len": 32, "landmarks": 21, "coords": 3, "dim": 2016},
        "files": {"weights": "model.npz", "onnx": "model.onnx"},
        "environment": {"mediapipe": mp_ver, "numpy": np.__version__},
        "evaluation": evaluation,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest_out, indent=2))
    logger.info(
        "Sign model trained: version=%s classes=%s clips=%d skipped=%d",
        version, model.classes, len(X_train), len(skipped),
    )
    return manifest_out
