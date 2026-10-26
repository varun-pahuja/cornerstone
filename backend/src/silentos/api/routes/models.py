"""Model registry: honest status from actually-present artifacts.

A configured path is never reported as a loaded model.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...schemas import ModelInfo, ModelRegistryStatus, ModelStatus
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/models", tags=["models"])

_REQUIRED_MANIFEST_KEYS = {"model_id", "version", "modality", "labels"}


def _scan(models_dir: Path) -> list[ModelInfo]:
    infos: list[ModelInfo] = []
    for modality in ("sign", "lip"):
        manifest = models_dir / modality / "manifest.json"
        if not manifest.exists():
            infos.append(
                ModelInfo(
                    model_id=modality,
                    modality=modality,
                    version="unknown",
                    status=ModelStatus.NOT_TRAINED,
                    path=None,
                    error=f"No model artifact: {manifest} does not exist",
                )
            )
            continue
        try:
            raw = json.loads(manifest.read_text())
            missing = _REQUIRED_MANIFEST_KEYS - raw.keys()
            if missing:
                raise ValueError(f"manifest missing keys: {sorted(missing)}")
        except (json.JSONDecodeError, ValueError) as e:
            infos.append(
                ModelInfo(
                    model_id=modality,
                    modality=modality,
                    version="unknown",
                    status=ModelStatus.ERROR,
                    path=str(manifest),
                    error=f"Invalid manifest: {e}",
                )
            )
            continue
        infos.append(
            ModelInfo(
                model_id=str(raw["model_id"]),
                modality=str(raw["modality"]),
                version=str(raw["version"]),
                status=ModelStatus.NOT_LOADED,  # artifact exists, loader runs in Phase 5/9
                path=str(manifest.parent),
                labels=list(raw["labels"]),
                input_shape=raw.get("input_shape"),
                preprocessing_version=raw.get("preprocessing_version"),
                evaluation=raw.get("evaluation"),
            )
        )
    return infos


@router.get("", response_model=ModelRegistryStatus)
def list_models(app: AppDep) -> ModelRegistryStatus:
    models = _scan(app.settings.paths.models_dir)
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
    for info in _scan(app.settings.paths.models_dir):
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
