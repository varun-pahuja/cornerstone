"""Dependency and offline diagnostics — real import/binary probes, no guessing."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import shutil
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from ...schemas import DependencyCheck, DiagnosticsReport
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/system", tags=["diagnostics"])

# import name -> (PyPI distribution name, required_for)
_PY_DEPS: dict[str, tuple[str, str]] = {
    "fastapi": ("fastapi", "API server"),
    "uvicorn": ("uvicorn", "API server"),
    "pydantic": ("pydantic", "settings + API schemas"),
    "cv2": ("opencv-python-headless", "frame preprocessing"),
    "numpy": ("numpy", "tensors"),
    "onnxruntime": ("onnxruntime", "ONNX inference"),
    "mediapipe": ("mediapipe", "hand/face landmarks (Phase 5/6)"),
    "torch": ("torch", "training (Phase 5/6)"),
    "pytest": ("pytest", "tests"),
}

# binary -> required_for
_BIN_DEPS: dict[str, str] = {
    "espeak-ng": "offline speech output (Phase 8)",
}


def _python_check(import_name: str, dist: str, required_for: str) -> DependencyCheck:
    available = importlib.util.find_spec(import_name) is not None
    version: str | None = None
    if available:
        try:
            version = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            version = None
    return DependencyCheck(
        name=dist, kind="python", available=available, version=version, required_for=required_for
    )


def _binary_check(binary: str, required_for: str) -> DependencyCheck:
    path = shutil.which(binary)
    return DependencyCheck(
        name=binary, kind="binary", available=path is not None, version=None, required_for=required_for
    )


@router.get("/dependencies", response_model=DiagnosticsReport)
def dependencies(app: AppDep) -> DiagnosticsReport:
    checks: list[DependencyCheck] = [
        _python_check(import_name, dist, why)
        for import_name, (dist, why) in _PY_DEPS.items()
    ]
    checks += [_binary_check(b, why) for b, why in _BIN_DEPS.items()]

    core = {c.name for c in checks if c.required_for.startswith(("API", "frame", "tensors"))}
    core_ok = all(c.available for c in checks if c.name in core)

    notes: list[str] = []
    missing = [c for c in checks if not c.available]
    for c in missing:
        notes.append(f"{c.name}: unavailable — required for {c.required_for}")
    if not missing:
        notes.append("All probed dependencies available")
    notes.append("No network calls are made by this endpoint")

    return DiagnosticsReport(
        dependencies=checks,
        offline_ok=core_ok,
        notes=notes,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/python")
def python_info() -> dict[str, Any]:
    return {
        "version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
    }
