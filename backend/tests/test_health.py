"""Health, status and metrics endpoint tests.

These run without any camera, model or hardware.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from silentos.config import PathsConfig, Settings
from silentos.main import create_app
from silentos.schemas import CameraState, ModelStatus, RuntimeState


@pytest.fixture
def client(tmp_path):
    settings = Settings(paths=PathsConfig.rooted(tmp_path))
    with TestClient(create_app(settings)) as c:
        yield c


def test_health_returns_ok_without_loading_models(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["schema_version"] == "1.0"
    datetime.fromisoformat(body["timestamp"])


def test_status_reports_honest_initial_state(client: TestClient):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    assert body["runtime_state"] == RuntimeState.STOPPED.value
    assert body["camera_state"] == CameraState.DISCONNECTED.value
    assert body["sign_model_status"] == ModelStatus.NOT_LOADED.value
    assert body["lip_model_status"] == ModelStatus.NOT_LOADED.value
    assert body["last_message"] is None
    assert body["last_recognition"] is None
    assert body["inference_latency_ms"] is None
    # camera provider comes from real config
    assert body["camera_provider"] == "video_file"


def test_system_metrics_returns_real_measurements(client: TestClient):
    r = client.get("/api/v1/system/metrics")
    assert r.status_code == 200
    body = r.json()
    # Real psutil values: percentages are always present
    assert isinstance(body["cpu_percent"], (int, float))
    assert 0.0 <= body["cpu_percent"] <= 100.0
    assert isinstance(body["memory_percent"], (int, float))
    assert body["memory_total_mb"] > 0
    assert body["hostname"]
    assert body["platform"]
    # temperature may legitimately be unavailable -> None allowed, never 0-fake
    if body["temperature_c"] is not None:
        assert -100 < body["temperature_c"] < 200


def test_settings_validated_with_rejects_bad_values():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings.model_validate({"fusion": {"sign_threshold": 1.5}})
    with pytest.raises(ValidationError):
        Settings.model_validate({"camera": {"provider": "not_a_provider"}})
    with pytest.raises(ValidationError):
        Settings.model_validate({"vocabulary": {"labels": ["A", "A"]}})


def test_load_settings_missing_file_raises(tmp_path):
    from silentos.config import load_settings

    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "nope.yaml")
