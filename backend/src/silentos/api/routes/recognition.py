"""Recognition status, lifecycle and history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ...schemas import ModelStatus, RecognitionStatus
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/recognition", tags=["recognition"])


@router.get("/status", response_model=RecognitionStatus)
def status(app: AppDep) -> RecognitionStatus:
    st = app.app_status()
    last = app.last_decision_view()
    return RecognitionStatus(
        runtime_state=st.runtime_state,
        mode=st.recognition_mode,
        sign_model=st.sign_model_status,
        lip_model=st.lip_model_status,
        frames_processed=app.frames_processed,
        last_decision=last,
        latency_ms=last.get("latency_ms") if last else None,
    )


@router.post("/start")
def start(app: AppDep) -> dict:
    detail = app.start_recognition()
    if detail is not None:
        raise HTTPException(status_code=503, detail=detail)
    return {"runtime_state": app.runtime_state.value}


@router.post("/stop")
def stop(app: AppDep) -> dict:
    detail = app.stop_recognition()
    if detail is not None:
        raise HTTPException(status_code=503, detail=detail)
    return {"runtime_state": app.runtime_state.value}


@router.get("/history")
def history(
    app: AppDep,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = app.db.list_history(limit=limit, offset=offset)
    for row in items:
        row["timestamp"] = row.pop("ts")
        row["accepted"] = bool(row["accepted"])
    return {"items": items, "total": app.db.count_history()}


@router.delete("/history")
def clear_history(app: AppDep) -> dict:
    return {"cleared": app.db.clear_history()}
