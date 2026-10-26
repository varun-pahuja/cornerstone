"""Phase 2 endpoint tests: settings, models, recognition, camera, datasets,
training, diagnostics. Real endpoints, honest states, no fabricated data.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from silentos.config import PathsConfig, Settings
from silentos.main import create_app
from silentos.schemas import CameraState, ModelStatus, RuntimeState


@pytest.fixture
def paths(tmp_path):
    return PathsConfig.rooted(tmp_path)


@pytest.fixture
def settings(paths):
    return Settings(paths=paths)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


# ---- settings ----


def test_settings_get_returns_full_view(client: TestClient):
    body = client.get("/api/v1/settings").json()
    assert body["recognition_mode"] == "both"
    assert body["vocabulary"]  # real canonical list from config
    assert "WATER" in body["vocabulary"] and "DOCTOR" in body["vocabulary"]
    assert body["abstain_label"] == "PLEASE REPEAT"
    assert "PLEASE REPEAT" not in body["vocabulary"]  # abstain label is separate
    assert body["requires_restart"] == []


def test_settings_put_updates_and_persists(client: TestClient):
    r = client.put("/api/v1/settings", json={"sign_threshold": 0.75})
    assert r.status_code == 200
    assert r.json()["sign_threshold"] == 0.75
    # applied to live controller
    assert client.get("/api/v1/status").json() is not None


def test_settings_put_rejects_out_of_range(client: TestClient):
    r = client.put("/api/v1/settings", json={"sign_threshold": 1.5})
    assert r.status_code == 422


def test_settings_camera_change_requires_restart(client: TestClient):
    body = client.put("/api/v1/settings", json={"camera_provider": "mock"}).json()
    assert body["camera_provider"] == "mock"
    assert "camera_provider" in body["requires_restart"]


def test_corrupt_overrides_do_not_block_startup(tmp_path):
    settings = Settings(paths=PathsConfig.rooted(tmp_path))
    app = create_app(settings)
    # simulate corrupt persisted overrides
    from silentos.database import Database

    db = Database(settings.paths.data_dir / "silentos.db")
    db.set_setting("settings.overrides", "{not json")
    with TestClient(app) as c:  # must not raise
        assert c.get("/api/v1/health").json()["status"] == "ok"


# ---- models ----


def test_models_honest_not_trained_without_artifacts(client: TestClient):
    body = client.get("/api/v1/models").json()
    assert len(body["models"]) == 2
    for m in body["models"]:
        assert m["status"] == ModelStatus.NOT_TRAINED.value
        assert "does not exist" in m["error"]
    assert body["sign_status"] == ModelStatus.NOT_TRAINED.value
    assert body["lip_status"] == ModelStatus.NOT_TRAINED.value


def test_models_valid_manifest_reports_not_loaded(client: TestClient, paths):
    paths.models_dir.mkdir(parents=True, exist_ok=True)
    (paths.models_dir / "sign").mkdir(exist_ok=True)
    (paths.models_dir / "sign" / "manifest.json").write_text(
        json.dumps(
            {
                "model_id": "sign",
                "modality": "sign",
                "version": "1.0.0",
                "labels": ["HELLO", "WATER"],
                "input_shape": [1, 150, 42],
                "preprocessing_version": "v1",
                "evaluation": {"val_accuracy": 0.71},
            }
        )
    )
    body = client.get("/api/v1/models").json()
    sign = next(m for m in body["models"] if m["modality"] == "sign")
    assert sign["status"] == ModelStatus.NOT_LOADED.value  # artifact exists, not loaded
    assert sign["labels"] == ["HELLO", "WATER"]
    lip = next(m for m in body["models"] if m["modality"] == "lip")
    assert lip["status"] == ModelStatus.NOT_TRAINED.value
    # /status agrees
    assert client.get("/api/v1/status").json()["sign_model_status"] == "NOT_LOADED"


def test_models_invalid_manifest_reports_error(client: TestClient, paths):
    (paths.models_dir / "lip").mkdir(parents=True, exist_ok=True)
    (paths.models_dir / "lip" / "manifest.json").write_text("{broken")
    body = client.get("/api/v1/models").json()
    lip = next(m for m in body["models"] if m["modality"] == "lip")
    assert lip["status"] == ModelStatus.ERROR.value


def test_model_load_rejected_until_phase_5(client: TestClient):
    r = client.post("/api/v1/models/sign/load")
    assert r.status_code == 409
    assert "Phase 5" in r.json()["detail"]


# ---- recognition ----


def test_recognition_status_honest_initial(client: TestClient):
    body = client.get("/api/v1/recognition/status").json()
    assert body["runtime_state"] == RuntimeState.STOPPED.value
    assert body["last_decision"] is None
    assert body["latency_ms"] is None


def test_recognition_start_rejected_until_models_trained(client: TestClient):
    r = client.post("/api/v1/recognition/start")
    assert r.status_code == 503
    assert "Phases 5" in r.json()["detail"]  # honest: models not trained yet
    # state unchanged
    assert client.get("/api/v1/recognition/status").json()["runtime_state"] == "STOPPED"


def test_recognition_history_empty_then_listed(client: TestClient, settings):
    body = client.get("/api/v1/recognition/history").json()
    assert body == {"items": [], "total": 0}

    # insert a real decision through the controller
    app = client.app.state.application
    app.db.add_history(
        {
            "timestamp": "2026-10-26T12:00:00Z",
            "mode": "both",
            "sign_label": "WATER",
            "sign_confidence": 0.82,
            "lip_label": None,
            "lip_confidence": None,
            "final_label": "WATER",
            "accepted": 1,
            "reason": "sign_only",
            "latency_ms": 12.5,
        }
    )
    body = client.get("/api/v1/recognition/history").json()
    assert body["total"] == 1
    assert body["items"][0]["timestamp"] == "2026-10-26T12:00:00Z"
    assert body["items"][0]["final_label"] == "WATER"
    assert body["items"][0]["accepted"] is True

    cleared = client.delete("/api/v1/recognition/history").json()
    assert cleared["cleared"] == 1
    assert client.get("/api/v1/recognition/history").json()["total"] == 0


# ---- camera ----


def test_camera_discovery_lists_all_providers(client: TestClient):
    body = client.get("/api/v1/cameras").json()
    providers = {c["provider"] for c in body}
    assert providers == {"video_file", "mock", "development_webcam", "pi_camera", "pi_usb_webcam"}
    pi = next(c for c in body if c["provider"] == "pi_camera")
    assert pi["available"] is False  # no Pi hardware here — honest


def test_camera_status_disconnected(client: TestClient):
    body = client.get("/api/v1/camera/status").json()
    assert body["state"] == CameraState.DISCONNECTED.value
    assert body["error"] is None


def test_camera_config_validated(client: TestClient):
    ok = client.put("/api/v1/camera/config", json={"target_fps": 15})
    assert ok.status_code == 200
    assert ok.json()["camera_target_fps"] == 15

    bad = client.put("/api/v1/camera/config", json={"provider": "hologram"})
    assert bad.status_code == 422


def test_camera_start_unconfigured_video_file_fails_honestly(client: TestClient):
    # Default provider is video_file with no path set -> real, honest failure.
    r = client.post("/api/v1/camera/start")
    assert r.status_code == 503
    assert "Video file not found" in r.json()["detail"]
    status = client.get("/api/v1/camera/status").json()
    assert status["state"] == "UNAVAILABLE"
    assert "Video file not found" in status["error"]
    # stopping returns to DISCONNECTED
    client.post("/api/v1/camera/stop")
    assert client.get("/api/v1/camera/status").json()["state"] == "DISCONNECTED"


def test_camera_capabilities_reports_real_devices_only(client: TestClient):
    body = client.get("/api/v1/camera/capabilities").json()
    assert isinstance(body["v4l2_devices"], list)
    for d in body["v4l2_devices"]:
        assert d["device_path"].startswith("/dev/video")
        assert d["name"]
    assert "video4linux" in body["note"]


# ---- datasets ----


def test_datasets_empty_stats_are_zero_not_fabricated(client: TestClient):
    assert client.get("/api/v1/datasets").json() == []
    stats = client.get("/api/v1/datasets/stats").json()
    assert stats["total_clips"] == 0
    assert stats["raw_video_files"] == 0
    assert stats["manifests"] == 0
    assert stats["by_class"] == {}


def test_dataset_stats_count_real_files(client: TestClient, paths):
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    (paths.raw_dir / "session1").mkdir(exist_ok=True)
    (paths.raw_dir / "session1" / "clip1.mp4").write_bytes(b"\x00")
    (paths.raw_dir / "clip2.webm").write_bytes(b"\x00")
    (paths.raw_dir / "notes.txt").write_text("not a video")

    stats = client.get("/api/v1/datasets/stats").json()
    assert stats["raw_video_files"] == 2
    assert stats["manifests"] == 0
    assert stats["total_clips"] == 0


# ---- training ----


def test_training_no_jobs_and_create_rejected(client: TestClient):
    assert client.get("/api/v1/training/jobs").json() == []
    r = client.post(
        "/api/v1/training/jobs", json={"modality": "sign", "dataset": "default"}
    )
    assert r.status_code == 409
    assert "Phase 5" in r.json()["detail"]
    assert client.get("/api/v1/training/jobs").json() == []  # still no fake job


def test_training_job_listing_and_cancel(client: TestClient):
    app = client.app.state.application
    job_id = app.db.create_job("sign", "default", {"total_epochs": 10})
    jobs = client.get("/api/v1/training/jobs").json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "QUEUED"
    assert jobs[0]["progress"] == 0.0

    detail = client.get(f"/api/v1/training/jobs/{job_id}").json()
    assert detail["job"]["id"] == job_id
    assert detail["logs"] == []

    cancelled = client.post(f"/api/v1/training/jobs/{job_id}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    assert client.get("/api/v1/training/jobs").json()[0]["status"] == "CANCELLED"

    missing = client.post("/api/v1/training/jobs/999/cancel")
    assert missing.status_code == 404


def test_training_job_not_found(client: TestClient):
    assert client.get("/api/v1/training/jobs/42").status_code == 404


# ---- diagnostics ----


def test_diagnostics_probes_real_dependencies(client: TestClient):
    body = client.get("/api/v1/system/dependencies").json()
    names = {d["name"] for d in body["dependencies"]}
    assert {"fastapi", "onnxruntime", "espeak-ng", "mediapipe"} <= names
    assert body["offline_ok"] is True  # core server deps present on this machine
    for d in body["dependencies"]:
        assert d["kind"] in ("python", "binary")
        assert d["required_for"]
    assert any("network" in n for n in body["notes"])


def test_python_info(client: TestClient):
    body = client.get("/api/v1/system/python").json()
    assert "3.14" in body["version"]
    assert body["platform"]
