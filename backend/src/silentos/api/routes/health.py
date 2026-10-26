"""Health, status and system metrics routes.

Health checks never load AI models.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ... import __version__
from ...schemas import SCHEMA_VERSION, AppStatus, HealthResponse, SystemMetrics
from ..deps import AppDep

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(app: AppDep) -> HealthResponse:
    app.db.count_history()  # cheap DB reachability check
    return HealthResponse(
        status="ok",
        version=__version__,
        schema_version=SCHEMA_VERSION,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/status", response_model=AppStatus)
def status(app: AppDep) -> AppStatus:
    return app.app_status()


@router.get("/system/metrics", response_model=SystemMetrics)
def system_metrics(app: AppDep) -> SystemMetrics:
    return app.system_metrics()
