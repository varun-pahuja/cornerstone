"""Dataset listing and statistics — reads real files, never fabricated counts."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ...schemas import DatasetStats, DatasetSummary
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])

_VIDEO_EXT = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def _scan(raw_dir: Path, manifests_dir: Path) -> tuple[list[DatasetSummary], DatasetStats]:
    raw_files = [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in _VIDEO_EXT]
    manifests = sorted(manifests_dir.glob("*.json"))

    summaries: list[DatasetSummary] = []
    by_class: dict[str, int] = {}
    by_modality: dict[str, int] = {}
    total_clips = 0

    for mf in manifests:
        try:
            raw = json.loads(mf.read_text())
        except (json.JSONDecodeError, OSError):
            raw = {}
        clips = raw.get("clips", [])
        dataset_id = str(raw.get("dataset_id", mf.stem))
        summaries.append(
            DatasetSummary(
                dataset_id=dataset_id,
                name=str(raw.get("name", mf.stem)),
                clip_count=len(clips),
                path=str(mf),
            )
        )
        for clip in clips:
            total_clips += 1
            cls = str(clip.get("label", "unknown"))
            by_class[cls] = by_class.get(cls, 0) + 1
            mod = str(clip.get("modality", "unknown"))
            by_modality[mod] = by_modality.get(mod, 0) + 1

    stats = DatasetStats(
        total_clips=total_clips,
        raw_video_files=len(raw_files),
        manifests=len(manifests),
        by_class=by_class,
        by_modality=by_modality,
    )
    return summaries, stats


@router.get("", response_model=list[DatasetSummary])
def list_datasets(app: AppDep) -> list[DatasetSummary]:
    summaries, _ = _scan(app.settings.paths.raw_dir, app.settings.paths.manifests_dir)
    return summaries


@router.get("/stats", response_model=DatasetStats)
def dataset_stats(app: AppDep) -> DatasetStats:
    _, stats = _scan(app.settings.paths.raw_dir, app.settings.paths.manifests_dir)
    return stats
