"""Training job listing. Creating jobs arrives with Phase 5 — rejected honestly."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...schemas import TrainingJobCreate, TrainingJobInfo
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/training", tags=["training"])


def _to_info(row: dict) -> TrainingJobInfo:
    return TrainingJobInfo(
        id=row["id"],
        created_at=row["created_at"],
        modality=row["modality"],
        dataset=row["dataset"],
        status=row["status"],
        progress=row["progress"],
        current_epoch=row["current_epoch"],
        total_epochs=row["total_epochs"],
        metrics=row["metrics"],
        error=row["error"],
    )


@router.get("/jobs", response_model=list[TrainingJobInfo])
def list_jobs(app: AppDep) -> list[TrainingJobInfo]:
    return [_to_info(r) for r in app.db.list_training_jobs()]


@router.get("/jobs/{job_id}")
def get_job(app: AppDep, job_id: int) -> dict:
    job = app.db.get_training_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return {"job": _to_info(job).model_dump(), "logs": app.db.get_training_logs(job_id)}


@router.post("/jobs", status_code=409)
def create_job(app: AppDep, body: TrainingJobCreate) -> dict:
    # Intentionally no job row: a queued job that never runs would be a lie.
    raise HTTPException(
        status_code=409,
        detail=(
            "Training pipeline not implemented yet (sign training arrives in "
            "Phase 5, silent-lip in Phase 6). No job was created."
        ),
    )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(app: AppDep, job_id: int) -> dict:
    job = app.db.get_training_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    if job["status"] in ("QUEUED", "RUNNING"):
        app.db.update_training_job(
            job_id, status="CANCELLED", error="Cancelled by user"
        )
    return {"id": job_id, "status": "CANCELLED" if job["status"] in ("QUEUED", "RUNNING") else job["status"]}
