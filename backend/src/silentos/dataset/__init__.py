"""Dataset engine: validation, manifests, deterministic participant splits,
clip recording and export.

Splits are participant-based (a participant appears in exactly one split) —
never random row splits. The assignment is a pure function of
(participants, seed, ratios), so it is reproducible and testable.
"""

from __future__ import annotations

import hashlib
import io
import json
import random
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

from ..schemas import (
    ClipMeta,
    ClipRecord,
    DatasetManifest,
    SplitResult,
    ValidationIssue,
    ValidationReport,
)

SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MIN_DURATION_S = 0.2
MAX_DURATION_S = 30.0
SPLIT_NAMES = ("train", "val", "test")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_clip(path: Path) -> dict[str, Any]:
    """Open a video with cv2 and return real facts, or raise ValueError."""
    if not path.is_file():
        raise ValueError("file does not exist")
    if path.stat().st_size == 0:
        raise ValueError("file is empty")
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError("video cannot be decoded (unsupported codec or corrupt)")
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frames <= 0:
            # some containers report 0 — count by reading
            frames = 0
            while True:
                ok, _ = cap.read()
                if not ok:
                    break
                frames += 1
        if frames <= 0:
            raise ValueError("video contains no decodable frames")
        if fps <= 0:
            fps = 30.0
    finally:
        cap.release()
    return {
        "frames": frames,
        "fps": round(fps, 3),
        "width": width,
        "height": height,
        "duration_s": round(frames / fps, 3),
    }


def validate_clip(
    meta: ClipMeta, file_path: Path, vocab: list[str], rel_file: str
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return (errors, warnings, probe) — probe is {} when unreadable."""
    errors: list[str] = []
    warnings: list[str] = []
    probe: dict[str, Any] = {}
    try:
        probe = probe_clip(file_path)
    except ValueError as e:
        errors.append(str(e))
    if not errors:
        if probe["duration_s"] < MIN_DURATION_S:
            errors.append(f"duration {probe['duration_s']}s < {MIN_DURATION_S}s minimum")
        elif probe["duration_s"] > MAX_DURATION_S:
            errors.append(f"duration {probe['duration_s']}s > {MAX_DURATION_S}s maximum")
        if probe["width"] < 64 or probe["height"] < 64:
            warnings.append(f"low resolution {probe['width']}x{probe['height']} (<64px)")
    if meta.label not in vocab:
        errors.append(f"label '{meta.label}' not in canonical vocabulary")
    if meta.modality not in ("sign", "lip"):
        errors.append(f"invalid modality '{meta.modality}'")
    for field_name, value in (
        ("participant_id", meta.participant_id),
        ("session_id", meta.session_id),
    ):
        if not SAFE_NAME.match(value):
            errors.append(f"{field_name} contains unsafe characters")
    return errors, warnings, probe


# ---- manifests ----

def manifest_path(manifests_dir: Path, dataset_id: str) -> Path:
    return manifests_dir / f"{dataset_id}.json"


def load_manifest(path: Path) -> DatasetManifest:
    raw = json.loads(path.read_text())
    return DatasetManifest.model_validate(raw)


def save_manifest(manifests_dir: Path, m: DatasetManifest) -> Path:
    m.updated_at = _now()
    m.clip_count = len(m.clips)
    path = manifest_path(manifests_dir, m.dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(m.model_dump(), indent=2))
    return path


def new_manifest(dataset_id: str, name: str | None = None) -> DatasetManifest:
    now = _now()
    return DatasetManifest(
        dataset_id=dataset_id,
        name=name or dataset_id,
        created_at=now,
        updated_at=now,
        clip_count=0,
        clips=[],
    )


def get_or_create_manifest(manifests_dir: Path, dataset_id: str) -> DatasetManifest:
    path = manifest_path(manifests_dir, dataset_id)
    if path.exists():
        return load_manifest(path)
    return new_manifest(dataset_id)


def register_clip(
    manifests_dir: Path,
    data_root: Path,
    meta: ClipMeta,
    source_file: Path,
    vocab: list[str],
) -> ClipRecord:
    """Validate + copy/place a file into data/raw and append it to the manifest.

    The file must already live under data_root (recorded or imported there);
    arbitrary paths outside the data root are rejected.
    """
    source_file = source_file.resolve()
    data_root = data_root.resolve()
    if not str(source_file).startswith(str(data_root)):
        raise ValueError(f"file must live under the data directory: {data_root}")

    errors, warnings, probe = validate_clip(meta, source_file, vocab, "")
    if errors:
        raise ValueError("; ".join(errors))

    rel = source_file.relative_to(data_root)
    record = ClipRecord(
        clip_id=f"clip_{uuid.uuid4().hex[:12]}",
        dataset_id=meta.dataset_id,
        file=str(rel),
        label=meta.label,
        modality=meta.modality,
        participant_id=meta.participant_id,
        session_id=meta.session_id,
        lighting=meta.lighting,
        notes=meta.notes,
        duration_s=probe["duration_s"],
        frames=probe["frames"],
        width=probe["width"],
        height=probe["height"],
        fps=probe["fps"],
        sha256=_sha256(source_file),
        split=None,
        created_at=_now(),
    )
    m = get_or_create_manifest(manifests_dir, meta.dataset_id)
    m.clips.append(record)
    save_manifest(manifests_dir, m)
    return record


# ---- splits (participant-based, deterministic) ----

def assign_splits(
    participants: list[str],
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> tuple[dict[str, str], list[str]]:
    """Pure function: (participants, seed, ratios) -> {participant: split}, warnings.

    Each participant lands in exactly one split. Assignment is a seeded shuffle
    of the sorted participant list, so the same inputs always give the same
    result. Test ratio is 1 - train - val.
    """
    warnings: list[str] = []
    parts = sorted(set(participants))
    n = len(parts)
    if n == 0:
        return {}, ["no participants to split"]
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio must be < 1.0")
    if n < 3:
        # not enough participants for three non-empty splits — all go to train
        warnings.append(
            f"only {n} participant(s): all assigned to train; record more participants "
            "for val/test splits"
        )
        return {p: "train" for p in parts}, warnings

    rng = random.Random(seed)
    rng.shuffle(parts)
    n_train = max(1, round(n * train_ratio))
    n_val = max(1, round(n * val_ratio))
    if n_train + n_val >= n:  # leave at least one for test
        n_val = max(1, n - n_train - 1)
    if n_train + n_val >= n:
        n_train = n - 2
    assignment: dict[str, str] = {}
    for i, p in enumerate(parts):
        if i < n_train:
            assignment[p] = "train"
        elif i < n_train + n_val:
            assignment[p] = "val"
        else:
            assignment[p] = "test"
    return assignment, warnings


def apply_splits(
    manifests_dir: Path,
    splits_dir: Path,
    dataset_id: str,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> SplitResult:
    m = load_manifest(manifest_path(manifests_dir, dataset_id))
    participants = sorted({c.participant_id for c in m.clips})
    assignment, warnings = assign_splits(participants, seed, train_ratio, val_ratio)
    for clip in m.clips:
        clip.split = assignment.get(clip.participant_id)
    m.splits = {
        "seed": seed,
        "ratios": {"train": train_ratio, "val": val_ratio, "test": round(1 - train_ratio - val_ratio, 4)},
        "participants": assignment,
        "generated_at": _now(),
    }
    save_manifest(manifests_dir, m)
    splits_dir.mkdir(parents=True, exist_ok=True)
    (splits_dir / f"{dataset_id}.json").write_text(
        json.dumps({"dataset_id": dataset_id, **m.splits}, indent=2)
    )
    counts: dict[str, int] = {s: 0 for s in SPLIT_NAMES}
    for c in m.clips:
        if c.split:
            counts[c.split] = counts.get(c.split, 0) + 1
    return SplitResult(
        dataset_id=dataset_id,
        seed=seed,
        ratios=m.splits["ratios"],
        participants=assignment,
        clip_counts=counts,
        warnings=warnings,
    )


# ---- validation report ----

def validate_dataset(
    manifests_dir: Path, data_root: Path, dataset_id: str, vocab: list[str]
) -> ValidationReport:
    m = load_manifest(manifest_path(manifests_dir, dataset_id))
    issues: list[ValidationIssue] = []
    valid = 0
    for clip in m.clips:
        errors, warnings, _ = validate_clip(
            _meta_from_clip(clip), data_root / clip.file, vocab, clip.file
        )
        if errors:
            issues.append(
                ValidationIssue(clip_id=clip.clip_id, file=clip.file, errors=errors, warnings=warnings)
            )
        else:
            valid += 1
            if warnings:
                issues.append(
                    ValidationIssue(clip_id=clip.clip_id, file=clip.file, errors=[], warnings=warnings)
                )
    return ValidationReport(
        dataset_id=dataset_id,
        checked=len(m.clips),
        valid=valid,
        invalid=len(m.clips) - valid,
        issues=issues,
        checked_at=datetime.now(timezone.utc),
    )


def _meta_from_clip(clip: ClipRecord) -> ClipMeta:
    return ClipMeta(
        label=clip.label,
        modality=clip.modality,  # type: ignore[arg-type]
        participant_id=clip.participant_id,
        session_id=clip.session_id,
        lighting=clip.lighting,
        notes=clip.notes,
        dataset_id=clip.dataset_id,
    )


# ---- export ----

def export_zip(manifests_dir: Path, data_root: Path, dataset_id: str, include_clips: bool) -> bytes:
    """Zip of manifest (+ splits + optionally the clip files)."""
    m = load_manifest(manifest_path(manifests_dir, dataset_id))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{dataset_id}/manifest.json", json.dumps(m.model_dump(), indent=2))
        if m.splits:
            zf.writestr(f"{dataset_id}/splits.json", json.dumps(m.splits, indent=2))
        if include_clips:
            for clip in m.clips:
                src = data_root / clip.file
                if src.is_file():
                    zf.write(src, f"{dataset_id}/clips/{clip.file}")
    return buf.getvalue()
