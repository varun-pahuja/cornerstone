"""Calibration endpoints — compute and apply per-user threshold profiles."""

from __future__ import annotations

from fastapi import APIRouter

from ...calibration import CalibrationEngine
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/calibration", tags=["calibration"])


@router.get("/profile")
def get_profile(app: AppDep) -> dict:
    """Compute (read-only) a calibration profile from recorded history."""
    eng = CalibrationEngine(app.db, app.settings)
    return eng.compute().to_dict()


@router.post("/apply")
def apply_profile(app: AppDep) -> dict:
    """Compute + persist the tuned thresholds into runtime settings."""
    eng = CalibrationEngine(app.db, app.settings)
    profile = eng.compute()
    if not profile.calibrated:
        return {"applied": False, "profile": profile.to_dict()}
    eng.apply(profile)
    # Persist overrides so they survive restart
    app.db.set_setting("settings.overrides", app.settings.model_dump(mode="json"))
    return {"applied": True, "profile": profile.to_dict()}
