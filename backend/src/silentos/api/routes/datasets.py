"""Dataset endpoints: record from camera, multipart import, register, validate,
participant-based splits, export. Counts and paths are always real."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated, Literal

import cv2
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from ...dataset import (
    export_zip,
    load_manifest,
    manifest_path,
    register_clip,
    validate_dataset,
)
from ...dataset import apply_splits as apply_splits_fn
from ...schemas import (
    ClipMeta,
    ClipRecord,
    DatasetStats,
    DatasetSummary,
    RecordRequest,
    SplitRequest,
    SplitResult,
    ValidationReport,
)
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])

_VIDEO_EXT = {".mp4", ".mov", ".webm", ".avi", ".mkv"}


def _scan(raw_dir: Path, manifests_dir: Path) -> tuple[list[DatasetSummary], DatasetStats]:
    raw_files = [p for p in raw_dir.rglob("*") if p.is_file() and p.suffix.lower() in _VIDEO_EXT]
    manifests = sorted(manifests_dir.glob("*.json"))

    summaries: list[DatasetSummary] = []
    by_class: dict[str, int] = {}
    by_modality: dict[str, int] = {}
    by_split: dict[str, int] = {}
    total_clips = 0

    for mf in manifests:
        try:
            raw = json.loads(mf.read_text())
        except (json.JSONDecodeError, OSError):
            raw = {}
        clips = raw.get("clips", [])
        summaries.append(
            DatasetSummary(
                dataset_id=str(raw.get("dataset_id", mf.stem)),
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
            sp = clip.get("split") or "unassigned"
            by_split[sp] = by_split.get(sp, 0) + 1

    stats = DatasetStats(
        total_clips=total_clips,
        raw_video_files=len(raw_files),
        manifests=len(manifests),
        by_class=by_class,
        by_modality=by_modality,
        by_split=by_split,
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


@router.post("/record", response_model=ClipRecord)
def record_clip(app: AppDep, body: RecordRequest) -> ClipRecord:
    """Record a clip from the running camera, validate it, register it."""
    if not app.camera.is_running:
        raise HTTPException(status_code=503, detail="Camera is not running — start it on Live Vision first")

    meta = body.meta
    if meta.label not in app.settings.vocabulary.labels:
        raise HTTPException(status_code=422, detail=f"Label '{meta.label}' not in vocabulary")

    raw_dir = (
        app.settings.paths.raw_dir / meta.participant_id / meta.session_id
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = raw_dir / f"rec-{stamp}-{meta.modality}.avi"

    fps = float(app.camera.status().get("fps") or 30.0)
    deadline = time.monotonic() + body.seconds
    writer: cv2.VideoWriter | None = None
    last_seq = -1
    frames = 0
    size: tuple[int, int] | None = None
    last_stale_check = time.monotonic()

    while time.monotonic() < deadline:
        packet = app.camera.latest_frame()
        now = time.monotonic()
        if packet is None or packet.seq == last_seq:
            if now - last_stale_check > 1.0 and packet is not None:
                if now - packet.captured_at > 2.0:
                    if writer is not None:
                        writer.release()
                    out_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=503, detail="Camera frames went stale during recording")
            time.sleep(0.005)
            continue
        last_stale_check = now
        frame = packet.frame
        h, w = frame.shape[:2]
        if writer is None:
            size = (w, h)
            writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
            if not writer.isOpened():
                raise HTTPException(status_code=500, detail="Could not open clip writer")
        if (w, h) != size:
            frame = cv2.resize(frame, size)
        writer.write(frame)
        last_seq = packet.seq
        frames += 1

    if writer is not None:
        writer.release()
    if frames < 3 or size is None:
        out_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"Recording produced only {frames} frame(s) — camera produced no usable video",
        )

    try:
        return register_clip(
            app.settings.paths.manifests_dir,
            app.settings.paths.data_dir,
            meta,
            out_path,
            list(app.settings.vocabulary.labels),
        )
    except ValueError as e:
        out_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/import", response_model=ClipRecord, status_code=201)
async def import_clip(
    app: AppDep,
    file: Annotated[UploadFile, File(description="Video clip")],
    label: Annotated[str, Form()],
    modality: Annotated[str, Form()],
    participant_id: Annotated[str, Form()],
    session_id: Annotated[str, Form()],
    lighting: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
    dataset_id: Annotated[str, Form()] = "default",
) -> ClipRecord:
    """Upload a clip file into the data root, validate, register."""
    try:
        meta = ClipMeta(
            label=label,
            modality=modality,  # type: ignore[arg-type]
            participant_id=participant_id,
            session_id=session_id,
            lighting=lighting,
            notes=notes,
            dataset_id=dataset_id,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid metadata: {e}") from e

    suffix = Path(file.filename or "clip.mp4").suffix.lower()
    if suffix not in _VIDEO_EXT:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}' — allowed: {sorted(_VIDEO_EXT)}",
        )
    dest_dir = app.settings.paths.raw_dir / meta.participant_id / meta.session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"import-{time.strftime('%Y%m%d-%H%M%S')}-{Path(file.filename).stem[:40]}{suffix}"
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 200 MB limit")
    dest.write_bytes(content)

    try:
        return register_clip(
            app.settings.paths.manifests_dir,
            app.settings.paths.data_dir,
            meta,
            dest,
            list(app.settings.vocabulary.labels),
        )
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/clips", response_model=ClipRecord, status_code=201)
def register_existing(app: AppDep, meta: ClipMeta, file: str = Query(..., description="Path under the data root")) -> ClipRecord:
    """Register a clip that already lives under data/ (e.g. produced by scripts)."""
    try:
        return register_clip(
            app.settings.paths.manifests_dir,
            app.settings.paths.data_dir,
            meta,
            app.settings.paths.data_dir / file,
            list(app.settings.vocabulary.labels),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{dataset_id}", response_model=object)
def get_dataset(app: AppDep, dataset_id: str) -> object:
    path = manifest_path(app.settings.paths.manifests_dir, dataset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return json.loads(path.read_text())


@router.post("/{dataset_id}/validate", response_model=ValidationReport)
def validate(app: AppDep, dataset_id: str) -> ValidationReport:
    path = manifest_path(app.settings.paths.manifests_dir, dataset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    return validate_dataset(
        app.settings.paths.manifests_dir,
        app.settings.paths.data_dir,
        dataset_id,
        list(app.settings.vocabulary.labels),
    )


@router.post("/{dataset_id}/splits", response_model=SplitResult)
def splits_generate(app: AppDep, dataset_id: str, body: SplitRequest) -> SplitResult:
    path = manifest_path(app.settings.paths.manifests_dir, dataset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    if body.train_ratio + body.val_ratio >= 1.0:
        raise HTTPException(status_code=422, detail="train_ratio + val_ratio must be < 1.0")
    try:
        return apply_splits_fn(
            app.settings.paths.manifests_dir,
            app.settings.paths.splits_dir,
            dataset_id,
            body.seed,
            body.train_ratio,
            body.val_ratio,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{dataset_id}/splits")
def splits_status(app: AppDep, dataset_id: str) -> dict:
    path = manifest_path(app.settings.paths.manifests_dir, dataset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    m = load_manifest(path)
    return {"dataset_id": dataset_id, "splits": m.splits}


@router.get("/{dataset_id}/export")
def export(
    app: AppDep,
    dataset_id: str,
    include_clips: Literal["true", "false"] = Query(default="true"),
) -> Response:
    path = manifest_path(app.settings.paths.manifests_dir, dataset_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")
    payload = export_zip(
        app.settings.paths.manifests_dir,
        app.settings.paths.data_dir,
        dataset_id,
        include_clips=include_clips == "true",
    )
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="dataset-{dataset_id}.zip"',
        },
    )
