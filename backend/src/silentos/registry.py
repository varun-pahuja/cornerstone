"""Model registry scanning — shared by the API routes and the controller.

Status semantics:
- NOT_TRAINED: no artifact on disk
- ERROR:       manifest present but unreadable/incomplete
- NOT_LOADED:  valid artifact exists, not yet loaded into memory
- LOADED:      loaded and ready (set by the loader, Phase 5/9)
"""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import ModelInfo, ModelStatus

_REQUIRED_MANIFEST_KEYS = {"model_id", "version", "modality", "labels"}


def scan_models(models_dir: Path) -> list[ModelInfo]:
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
        except (json.JSONDecodeError, OSError, ValueError) as e:
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
                status=ModelStatus.NOT_LOADED,
                path=str(manifest.parent),
                labels=list(raw["labels"]),
                input_shape=raw.get("input_shape"),
                preprocessing_version=raw.get("preprocessing_version"),
                evaluation=raw.get("evaluation"),
            )
        )
    return infos


def status_for(models_dir: Path, modality: str) -> ModelStatus:
    for info in scan_models(models_dir):
        if info.modality == modality:
            return info.status
    return ModelStatus.ERROR
