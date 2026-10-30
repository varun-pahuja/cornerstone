"""Training jobs: sign training runs in-process (Phase 5).

Honesty rules:
- validation/precheck failures happen BEFORE any job row exists (409 + "No job
  was created.")
- one job at a time (non-blocking lock -> 409), cancellable per epoch
- progress, logs and metrics only ever reflect the real run
"""

from __future__ import annotations

import json
import logging
import threading

from fastapi import APIRouter, HTTPException

from ...schemas import TrainingJobCreate, TrainingJobInfo
from ...sign.train import TrainingError as SignTrainingError
from ...sign.train import train_sign, validate_request as validate_sign_request
from ...lip.train import TrainingError as LipTrainingError
from ...lip.train import train_lip, validate_request as validate_lip_request
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/training", tags=["training"])
logger = logging.getLogger("silentos.training")

# Single-process backend: at most one training run at a time.
_TRAINING_LOCK = threading.Lock()

_ALLOWED_CONFIG = ("seed", "epochs", "lr", "l2")
_DEFAULTS = {"seed": 42, "epochs": 40, "lr": 0.5, "l2": 1e-3}


class _Cancelled(Exception):
    """Raised inside the worker when the job row was cancelled."""


def _parse(value):
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


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
        metrics=_parse(row["metrics"]),
        error=row["error"],
    )


def _validated_config(config: dict) -> dict:
    """Strict config: unknown keys and out-of-range values are 400, never ignored."""
    unknown = sorted(set(config) - set(_ALLOWED_CONFIG))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown training config key(s): {', '.join(unknown)} — "
                f"allowed: {', '.join(_ALLOWED_CONFIG)}"
            ),
        )
    out = dict(_DEFAULTS)
    for key, value in config.items():
        if key in ("seed", "epochs"):
            if isinstance(value, bool) or not isinstance(value, int):
                raise HTTPException(status_code=400, detail=f"config.{key} must be an integer")
            if key == "seed" and value < 0:
                raise HTTPException(status_code=400, detail="config.seed must be >= 0")
            if key == "epochs" and not 1 <= value <= 500:
                raise HTTPException(status_code=400, detail="config.epochs must be 1..500")
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(status_code=400, detail=f"config.{key} must be a number")
            if key == "lr" and not 0 < float(value) <= 10:
                raise HTTPException(status_code=400, detail="config.lr must be in (0, 10]")
            if key == "l2" and not 0 <= float(value) <= 10:
                raise HTTPException(status_code=400, detail="config.l2 must be in [0, 10]")
        out[key] = value
    return out


def _flat_metrics(manifest: dict) -> dict:
    """One-level metrics so the dashboard can render every real number directly."""
    ev = manifest.get("evaluation", {})
    train = ev.get("train") or {}
    metrics: dict = {
        "version": manifest.get("version"),
        "labels": ", ".join(manifest.get("labels") or []),
        "clips_used": ev.get("clips_used"),
        "final_loss": ev.get("final_loss"),
        "train_accuracy": train.get("accuracy"),
        "train_macro_f1": train.get("macro_f1"),
        "train_per_class": train.get("per_class"),
    }
    for split in ("val", "test"):
        block = ev.get(split)
        if isinstance(block, dict) and "accuracy" in block:
            metrics[f"{split}_accuracy"] = block["accuracy"]
            metrics[f"{split}_macro_f1"] = block.get("macro_f1")
            metrics[f"{split}_per_class"] = block.get("per_class")
    return metrics


def _run_job(app, job_id: int, dataset_id: str, config: dict) -> None:
    """Worker thread body: always releases the lock, never leaves a job RUNNING."""
    db = app.db
    try:
        row = db.get_job(job_id)
        if row is None or row["status"] == "CANCELLED":
            raise _Cancelled()

        def progress(epoch: int, total: int, loss: float) -> None:
            row = db.get_job(job_id)
            if row is None or row["status"] == "CANCELLED":
                raise _Cancelled()
            db.update_job(
                job_id,
                status="RUNNING",
                current_epoch=epoch,
                total_epochs=total,
                progress=round(epoch / total, 4) if total else 0.0,
            )
            db.append_job_log(job_id, f"epoch {epoch}/{total} loss={loss:.4f}")

        db.update_job(job_id, status="RUNNING")
        db.append_job_log(
            job_id,
            f"training started: dataset={dataset_id} "
            + " ".join(f"{k}={config[k]}" for k in sorted(config)),
        )
        if row["modality"] == "lip":
            manifest = train_lip(
                settings=app.settings,
                dataset_id=dataset_id,
                seed=config["seed"],
                epochs=config["epochs"],
                lr=config["lr"],
                l2=config["l2"],
                progress_cb=progress,
            )
        else:
            manifest = train_sign(
                settings=app.settings,
                dataset_id=dataset_id,
                seed=config["seed"],
                epochs=config["epochs"],
                lr=config["lr"],
                l2=config["l2"],
                progress_cb=progress,
            )
        metrics = _flat_metrics(manifest)
        db.append_job_log(
            job_id,
            f"exported {row['modality']} model version={metrics['version']} "
            f"train_accuracy={metrics['train_accuracy']} "
            f"train_macro_f1={metrics['train_macro_f1']}",
        )
        db.update_job(
            job_id,
            status="COMPLETED",
            progress=1.0,
            current_epoch=config["epochs"],
            total_epochs=config["epochs"],
            metrics=json.dumps(metrics),
            error=None,
        )
        logger.info("Training job %d completed (version=%s)", job_id, metrics["version"])
    except _Cancelled:
        db.update_job(job_id, status="CANCELLED", error="Cancelled by user")
        db.append_job_log(job_id, "cancelled by user")
    except (SignTrainingError, LipTrainingError) as e:
        db.update_job(job_id, status="FAILED", error=str(e))
        db.append_job_log(job_id, f"failed: {e}")
        logger.warning("Training job %d failed: %s", job_id, e)
    except Exception as e:  # noqa: BLE001 — crash must be visible, never silent
        logger.exception("Training job %d crashed", job_id)
        db.update_job(job_id, status="FAILED", error=f"Training crashed: {e}")
        db.append_job_log(job_id, f"crashed: {type(e).__name__}: {e}")
    finally:
        _TRAINING_LOCK.release()


@router.get("/jobs", response_model=list[TrainingJobInfo])
def list_jobs(app: AppDep) -> list[TrainingJobInfo]:
    return [_to_info(r) for r in app.db.list_jobs()]


@router.get("/jobs/{job_id}")
def get_job(app: AppDep, job_id: int) -> dict:
    job = app.db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    return {"job": _to_info(job).model_dump(), "logs": _parse(job.get("logs")) or []}


@router.post("/jobs", status_code=201)
def create_job(app: AppDep, body: TrainingJobCreate) -> dict:
    config = _validated_config(body.config)

    if not _TRAINING_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="A training job is already running. No job was created.",
        )

    try:
        # Precheck before any row exists: a queued job that can never run is a lie.
        if body.modality == "lip":
            validate_lip_request(app.settings, body.dataset)
        else:
            validate_sign_request(app.settings, body.dataset)
    except (SignTrainingError, LipTrainingError) as e:
        _TRAINING_LOCK.release()
        raise HTTPException(status_code=409, detail=f"{e}. No job was created.") from e

    job_id = app.db.create_job(body.modality, body.dataset, config)
    try:
        threading.Thread(
            target=_run_job, args=(app, job_id, body.dataset, config), daemon=True
        ).start()
    except Exception:
        _TRAINING_LOCK.release()
        app.db.update_job(job_id, status="FAILED", error="Could not start worker thread")
        raise
    return {"job": _to_info(app.db.get_job(job_id)).model_dump()}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(app: AppDep, job_id: int) -> dict:
    job = app.db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found")
    if job["status"] in ("QUEUED", "RUNNING"):
        app.db.update_job(job_id, status="CANCELLED", error="Cancelled by user")
    return {
        "id": job_id,
        "status": "CANCELLED" if job["status"] in ("QUEUED", "RUNNING") else job["status"],
    }
