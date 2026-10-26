"""Phase 4 dataset engine tests: probe/validation, manifests, participant
splits, record-from-camera, multipart import, export. Real files only."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from silentos.config import PathsConfig, Settings
from silentos.dataset import (
    apply_splits,
    assign_splits,
    export_zip,
    load_manifest,
    manifest_path,
    probe_clip,
    register_clip,
    validate_dataset,
)
from silentos.main import create_app
from silentos.schemas import ClipMeta

VOCAB = ["HELP", "WATER", "FOOD", "PAIN", "YES", "NO", "STOP", "DOCTOR", "TOILET", "THANK YOU"]


def wait_for(predicate, timeout=5.0, interval=0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def write_clip(path: Path, frames: int = 15, size=(160, 120), fps: float = 30.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    assert out.isOpened()
    for i in range(frames):
        out.write(np.full((size[1], size[0], 3), (i * 7) % 255, dtype=np.uint8))
    out.release()
    return path


def meta(**kw) -> ClipMeta:
    base = dict(
        label="WATER", modality="sign", participant_id="p01", session_id="s1",
        dataset_id="default",
    )
    base.update(kw)
    return ClipMeta(**base)


# ---- probe / validation ----


def test_probe_reads_real_facts(tmp_path):
    p = write_clip(tmp_path / "c.avi", frames=15, fps=30.0)
    facts = probe_clip(p)
    assert facts["frames"] == 15
    assert facts["width"] == 160 and facts["height"] == 120
    assert abs(facts["duration_s"] - 0.5) < 0.05


def test_probe_rejects_missing_empty_and_corrupt(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        probe_clip(tmp_path / "nope.avi")
    empty = tmp_path / "empty.avi"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        probe_clip(empty)
    corrupt = tmp_path / "corrupt.avi"
    corrupt.write_bytes(b"this is not a video file at all")
    with pytest.raises(ValueError):
        probe_clip(corrupt)


def test_register_rejects_bad_label(tmp_path):
    src = write_clip(tmp_path / "raw/c.avi")
    with pytest.raises(ValueError, match="not in canonical vocabulary"):
        register_clip(tmp_path / "manifests", tmp_path, meta(label="HELLO"), src, VOCAB)


def test_register_rejects_unsafe_participant(tmp_path):
    src = write_clip(tmp_path / "raw/c.avi")
    with pytest.raises(ValueError):
        # pydantic pattern blocks this at the schema layer
        meta(participant_id="../evil")


def test_register_rejects_file_outside_data_root(tmp_path):
    outside = write_clip(tmp_path.parent / "outside.avi")
    with pytest.raises(ValueError, match="under the data directory"):
        register_clip(tmp_path / "manifests", tmp_path / "data", meta(), outside, VOCAB)
    outside.unlink(missing_ok=True)


def test_register_produces_real_manifest_entry(tmp_path):
    data = tmp_path / "data"
    src = write_clip(data / "raw" / "p01" / "s1" / "c.avi")
    rec = register_clip(tmp_path / "manifests", data, meta(), src, VOCAB)
    assert rec.duration_s > 0 and rec.frames == 15
    assert len(rec.sha256) == 64
    m = load_manifest(manifest_path(tmp_path / "manifests", "default"))
    assert m.clip_count == 1
    assert m.clips[0].clip_id == rec.clip_id


# ---- splits ----


def test_splits_deterministic_and_disjoint():
    people = [f"p{i:02d}" for i in range(10)]
    a1, w1 = assign_splits(people, seed=42, train_ratio=0.7, val_ratio=0.15)
    a2, _ = assign_splits(list(reversed(people)), seed=42, train_ratio=0.7, val_ratio=0.15)
    assert a1 == a2  # same participants + seed -> identical (order-independent)
    assert w1 == []
    # every participant in exactly one split
    assert set(a1) == set(people)
    assert set(a1.values()) <= {"train", "val", "test"}
    counts = {s: list(a1.values()).count(s) for s in ("train", "val", "test")}
    assert counts["train"] >= 1 and counts["val"] >= 1 and counts["test"] >= 1
    assert counts["train"] == 7  # 70% of 10


def test_splits_different_seed_changes_assignment():
    people = [f"p{i:02d}" for i in range(20)]
    a1, _ = assign_splits(people, seed=1, train_ratio=0.7, val_ratio=0.15)
    a2, _ = assign_splits(people, seed=2, train_ratio=0.7, val_ratio=0.15)
    assert a1 != a2


def test_splits_single_participant_all_train_with_warning():
    a, warnings = assign_splits(["only"], seed=42, train_ratio=0.7, val_ratio=0.15)
    assert a == {"only": "train"}
    assert warnings and "record more participants" in warnings[0]


def test_splits_reject_bad_ratios():
    with pytest.raises(ValueError, match="must be < 1.0"):
        assign_splits(["a", "b", "c"], seed=1, train_ratio=0.7, val_ratio=0.3)


def test_apply_splits_updates_manifest_and_writes_file(tmp_path):
    manifests = tmp_path / "manifests"
    data = tmp_path / "data"
    for pid in ("p01", "p02", "p03"):
        write_clip(data / "raw" / pid / "s1" / "c.avi")
        register_clip(manifests, data, meta(participant_id=pid), data / "raw" / pid / "s1" / "c.avi", VOCAB)
    result = apply_splits(manifests, tmp_path / "splits", "default", seed=42,
                          train_ratio=0.7, val_ratio=0.15)
    # 3 participants -> 3 non-empty splits (1/1/1); every clip gets a split
    assert sum(result.clip_counts.values()) == 3
    assert set(result.participants) == {"p01", "p02", "p03"}
    m = load_manifest(manifest_path(manifests, "default"))
    assert all(c.split in ("train", "val", "test") for c in m.clips)
    assert (tmp_path / "splits" / "default.json").is_file()


# ---- API ----


@pytest.fixture
def client(tmp_path):
    settings = Settings(paths=PathsConfig.rooted(tmp_path))
    with TestClient(create_app(settings)) as c:
        yield c


def test_record_from_mock_camera(client: TestClient):
    client.put("/api/v1/camera/config", json={"provider": "mock"})
    # camera off -> honest 503
    r = client.post(
        "/api/v1/datasets/record",
        json={"seconds": 0.5, "meta": meta().model_dump()},
    )
    assert r.status_code == 503
    assert "Camera is not running" in r.json()["detail"]

    assert client.post("/api/v1/camera/start").status_code == 200
    try:
        r = client.post(
            "/api/v1/datasets/record",
            json={"seconds": 0.6, "meta": meta().model_dump()},
        )
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["frames"] >= 3
        assert rec["sha256"]
        # file really exists on disk
        assert (Path(client.app.state.application.settings.paths.data_dir) / rec["file"]).is_file()
        # appears in stats
        stats = client.get("/api/v1/datasets/stats").json()
        assert stats["total_clips"] == 1
        assert stats["by_class"]["WATER"] == 1
    finally:
        client.post("/api/v1/camera/stop")


def test_record_rejects_label_not_in_vocabulary(client: TestClient):
    client.put("/api/v1/camera/config", json={"provider": "mock"})
    client.post("/api/v1/camera/start")
    try:
        r = client.post(
            "/api/v1/datasets/record",
            json={"seconds": 0.5, "meta": meta(label="HELLO").model_dump()},
        )
        assert r.status_code == 422
        assert "vocabulary" in r.json()["detail"]
    finally:
        client.post("/api/v1/camera/stop")


def test_multipart_import_roundtrip(client: TestClient, tmp_path):
    clip = write_clip(tmp_path / "upload.avi", frames=12)
    r = client.post(
        "/api/v1/datasets/import",
        files={"file": ("upload.avi", clip.read_bytes(), "video/x-msvideo")},
        data={
            "label": "FOOD", "modality": "lip", "participant_id": "p07",
            "session_id": "s2", "lighting": "indoor",
        },
    )
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["label"] == "FOOD" and rec["modality"] == "lip"
    assert rec["frames"] == 12

    # wrong extension rejected
    r = client.post(
        "/api/v1/datasets/import",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"label": "FOOD", "modality": "lip", "participant_id": "p07", "session_id": "s2"},
    )
    assert r.status_code == 422
    assert "Unsupported file type" in r.json()["detail"]

    # label outside vocabulary rejected, file removed
    r = client.post(
        "/api/v1/datasets/import",
        files={"file": ("clip.avi", clip.read_bytes(), "video/x-msvideo")},
        data={"label": "ELEPHANT", "modality": "sign", "participant_id": "p07", "session_id": "s2"},
    )
    assert r.status_code == 422
    assert client.get("/api/v1/datasets/stats").json()["total_clips"] == 1  # first import only


def test_validate_reports_missing_file(client: TestClient, tmp_path):
    clip = write_clip(tmp_path / "u.avi")
    client.post(
        "/api/v1/datasets/import",
        files={"file": ("u.avi", clip.read_bytes(), "video/x-msvideo")},
        data={"label": "YES", "modality": "sign", "participant_id": "p01", "session_id": "s1"},
    )
    app = client.app.state.application
    manifest = json.loads(
        (app.settings.paths.manifests_dir / "default.json").read_text()
    )
    (app.settings.paths.data_dir / manifest["clips"][0]["file"]).unlink()  # simulate loss

    r = client.post("/api/v1/datasets/default/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] == 1 and body["invalid"] == 1
    assert any("does not exist" in e for e in body["issues"][0]["errors"])


def test_splits_endpoint_and_export(client: TestClient, tmp_path):
    # three participants so splits are meaningful
    for pid in ("p01", "p02", "p03"):
        clip = write_clip(tmp_path / f"{pid}.avi")
        client.post(
            "/api/v1/datasets/import",
            files={"file": (f"{pid}.avi", clip.read_bytes(), "video/x-msvideo")},
            data={"label": "PAIN", "modality": "sign", "participant_id": pid, "session_id": "s1"},
        )

    r = client.post("/api/v1/datasets/default/splits", json={"seed": 42})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["participants"]) == {"p01", "p02", "p03"}
    assert sum(body["clip_counts"].values()) == 3
    assert body["participants"] == body["participants"]  # stable
    # deterministic: same seed again -> identical
    r2 = client.post("/api/v1/datasets/default/splits", json={"seed": 42})
    assert r2.json()["participants"] == body["participants"]

    status = client.get("/api/v1/datasets/default/splits").json()
    assert status["splits"]["seed"] == 42

    # bad ratios rejected
    bad = client.post(
        "/api/v1/datasets/default/splits",
        json={"seed": 1, "train_ratio": 0.7, "val_ratio": 0.3},
    )
    assert bad.status_code == 422

    # export: zip with manifest + splits + clips
    exp = client.get("/api/v1/datasets/default/export")
    assert exp.status_code == 200
    assert exp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(exp.content))
    names = zf.namelist()
    assert "default/manifest.json" in names
    assert "default/splits.json" in names
    assert any(n.startswith("default/clips/") for n in names)
    manifest = json.loads(zf.read("default/manifest.json"))
    assert manifest["clip_count"] == 3

    # metadata-only export excludes clips
    exp2 = client.get("/api/v1/datasets/default/export?include_clips=false")
    zf2 = zipfile.ZipFile(io.BytesIO(exp2.content))
    assert not any(n.startswith("default/clips/") for n in zf2.namelist())


def test_dataset_404s(client: TestClient):
    assert client.get("/api/v1/datasets/nope").status_code == 404
    assert client.post("/api/v1/datasets/nope/validate").status_code == 404
    assert client.post("/api/v1/datasets/nope/splits", json={}).status_code == 404
    assert client.get("/api/v1/datasets/nope/export").status_code == 404
