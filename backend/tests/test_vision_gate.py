"""Extraction gate: the API must refuse work instead of dying with the host.

On some hosts MediaPipe extraction is SIGKILLed (T-ML-01) and the kill lands
inside uvicorn itself — no in-process catch exists. The gate probes once in a
child process and both refusal paths stub that verdict, so these tests are
deterministic on every machine (dead host, good host, CI).
"""

from __future__ import annotations

import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from silentos.config import PathsConfig, Settings
from silentos.main import create_app
from silentos.schemas import RuntimeState
from test_sign import manifest_with

DEAD = (False, "Landmark extraction was killed outright (signal 9) on this host")


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(paths=PathsConfig.rooted(tmp_path))
    s.paths.ensure()
    return s


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def test_probe_translates_child_signal_into_honest_failure(monkeypatch):
    from silentos import vision_gate

    killed = subprocess.CompletedProcess([], returncode=-9, stdout="", stderr="")
    monkeypatch.setattr(vision_gate.subprocess, "run", lambda *a, **k: killed)
    ok, why = vision_gate.probe_extraction(vision_gate.Path("/raw"), vision_gate.Path("/m.task"))
    assert ok is False
    assert "signal 9" in why
    assert "T-ML-01" in why

    fine = subprocess.CompletedProcess(
        [], returncode=0, stdout="PROBE_OK\n", stderr=""
    )
    monkeypatch.setattr(vision_gate.subprocess, "run", lambda *a, **k: fine)
    assert vision_gate.probe_extraction(
        vision_gate.Path("/raw"), vision_gate.Path("/m.task")
    ) == (True, "")


def test_training_job_refused_when_extraction_is_dead(client: TestClient, monkeypatch):
    app = client.app.state.application
    manifest_with(
        app.settings,
        "gate",
        [("p01", "WATER"), ("p01", "FOOD"), ("p02", "WATER"), ("p02", "FOOD")],
        splits={"participants": {"p01": "train", "p02": "train"}},
    )
    monkeypatch.setattr(app, "extraction_probe", lambda: DEAD)

    r = client.post(
        "/api/v1/training/jobs", json={"modality": "sign", "dataset": "gate"}
    )
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "signal 9" in detail
    assert "Colab" in detail
    assert "No job was created" in detail
    assert client.get("/api/v1/training/jobs").json() == []


def test_recognition_start_refused_when_extraction_is_dead(
    client: TestClient, monkeypatch
):
    app = client.app.state.application
    paths = app.settings.paths
    sign_dir = paths.models_dir / "sign"
    sign_dir.mkdir(parents=True, exist_ok=True)
    # Manifest only: registry reports NOT_LOADED (i.e. trained), which is what
    # gets us past the not-trained guard — the gate must refuse next.
    (sign_dir / "manifest.json").write_text(
        json.dumps(
            {
                "model_id": "sign",
                "modality": "sign",
                "version": "1.0.0",
                "labels": ["YES", "NO"],
                "input_shape": [1, 2016],
                "preprocessing_version": "sign_v1",
                "evaluation": {"val_accuracy": 0.5},
            }
        )
    )
    monkeypatch.setattr(app, "extraction_probe", lambda: DEAD)

    r = client.post("/api/v1/recognition/start")
    assert r.status_code == 503
    assert "signal 9" in r.json()["detail"]
    assert "No state change" in r.json()["detail"]
    assert (
        client.get("/api/v1/recognition/status").json()["runtime_state"]
        == RuntimeState.STOPPED.value
    )
