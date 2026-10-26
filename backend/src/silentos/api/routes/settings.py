"""Settings endpoints: validated partial updates, persisted overrides."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas import SettingsUpdate, SettingsView
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsView)
def get_settings(app: AppDep) -> SettingsView:
    return SettingsView(**app.settings_view())


@router.put("", response_model=SettingsView)
def update_settings(app: AppDep, update: SettingsUpdate) -> SettingsView:
    # Pydantic bounds-checks every field; None means "unchanged".
    applied = app.apply_settings(update.model_dump(exclude_none=True))
    return SettingsView(**applied)
