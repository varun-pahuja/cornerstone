"""Model registry: honest status from actually-present artifacts.

A configured path is never reported as a loaded model.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...registry import scan_models
from ...schemas import ModelInfo, ModelRegistryStatus, ModelStatus
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/models", tags=["models"])

@router.get("", response_model=ModelRegistryStatus)
def list_models(app: AppDep) -> ModelRegistryStatus:
    models = scan_models(app.settings.paths.models_dir)
    by_modality = {m.modality: m for m in models}
    return ModelRegistryStatus(
        models=models,
        sign_status=by_modality["sign"].status,
        lip_status=by_modality["lip"].status,
    )


@router.get("/{model_id}", response_model=ModelInfo)
def get_model(app: AppDep, model_id: str) -> ModelInfo:
    if model_id not in ("sign", "lip"):
        raise HTTPException(status_code=404, detail=f"Unknown model id: {model_id}")
    for info in scan_models(app.settings.paths.models_dir):
        if info.modality == model_id:
            return info
    raise HTTPException(status_code=404, detail="Model not found")


@router.post("/{model_id}/load")
def load_model(app: AppDep, model_id: str) -> dict:
    if model_id not in ("sign", "lip"):
        raise HTTPException(status_code=404, detail=f"Unknown model id: {model_id}")
    raise HTTPException(
        status_code=409,
        detail=(
            "Model loader not implemented yet (validation + inference arrive in "
            "Phase 5/9). Nothing was loaded."
        ),
    )
