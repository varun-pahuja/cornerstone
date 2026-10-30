"""Phase 5 tests: feature math, baseline model, train_sign e2e (injected
extractor), and the training-route worker (real rows/logs/lock, stubbed trainer).

Honesty rules under test: metrics only from real computation, validation
rejections leave no job rows, cancellation and restart reconcile are observable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from silentos.api.routes import training as training_route
from silentos.config import PathsConfig, Settings
from silentos.dataset import load_manifest, manifest_path, new_manifest, register_clip, save_manifest
from silentos.main import create_app
from silentos.schemas import ClipMeta, ClipRecord
from silentos.sign.features import (
    FEATURE_DIM,
    MIN_FRAMES,
    SEQ_LEN,
    normalize_landmarks,
    resample,
    sequence_to_features,
)
from silentos.sign.model import BaselineNotTrained, LogisticBaseline
from silentos.sign.train import (
    MIN_CLASSES,
    MIN_TRAIN_CLIPS,
    TrainingError,
    train_sign,
    validate_request,
)

VOCAB = ["HELP", "WATER", "FOOD", "PAIN", "YES", "NO", "STOP", "DOCTOR", "TOILET", "THANK YOU"]


def wait_for(predicate, timeout=10.0, interval=0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ---- fixtures / helpers ----


def write_const_clip(path: Path, value: int, frames: int = 25, size=(160, 120), fps: float = 30.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
    assert out.isOpened()
    for _ in range(frames):
        out.write(np.full((size[1], size[0], 3), value, dtype=np.uint8))
    out.release()
    return path


def meta(**kw) -> ClipMeta:
    base = dict(
        label="WATER", modality="sign", participant_id="p01", session_id="s1",
        dataset_id="default",
    )
    base.update(kw)
    return ClipMeta(**base)


class PatternExtractor:
    """Injected HandExtractor stand-in: landmark SHAPE encodes frame brightness,
    so the two classes stay separable after wrist/scale normalization."""

    def extract(self, frame: np.ndarray) -> np.ndarray | None:
        bright = float(frame.mean()) > 127
        idx = np.arange(21, dtype=np.float64)
        x = idx / 20.0
        y = np.sqrt(np.clip(1.0 - (2.0 * x - 1.0) ** 2, 0.0, 1.0)) if bright else x**2
        return np.stack([x, y, np.full(21, 0.5)], axis=1)


def manifest_with(settings, dataset_id: str, clips: list[tuple[str, str]], splits: dict | None) -> None:
    """Write a manifest directly (validate_request is manifest-level; no videos)."""
    m = new_manifest(dataset_id)
    for i, (pid, label) in enumerate(clips):
        m.clips.append(
            ClipRecord(
                clip_id=f"clip_{i:03d}",
                dataset_id=dataset_id,
                file=f"raw/{pid}/s1/c{i}.avi",
                label=label,
                modality="sign",
                participant_id=pid,
                session_id="s1",
                duration_s=1.0,
                frames=30,
                width=160,
                height=120,
                fps=30.0,
                sha256="0" * 64,
                split=None,
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    m.splits = splits
    save_manifest(settings.paths.manifests_dir, m)


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(paths=PathsConfig.rooted(tmp_path))
    s.paths.ensure()
    return s


@pytest.fixture
def sign_dataset(settings) -> Settings:
    """Real 25-frame clips: 4 train (2 classes x 2 participants) + 1 val clip."""
    paths = settings.paths
    specs = [
        ("p01", "WATER", 255), ("p01", "FOOD", 0),
        ("p02", "WATER", 255), ("p02", "FOOD", 0),
        ("p03", "WATER", 255),  # -> val
    ]
    for i, (pid, label, value) in enumerate(specs):
        path = paths.data_dir / f"raw/{pid}/s1/c{i}.avi"
        write_const_clip(path, value=value)
        register_clip(paths.manifests_dir, paths.data_dir, meta(label=label, participant_id=pid), path, VOCAB)
    m = load_manifest(manifest_path(paths.manifests_dir, "default"))
    m.splits = {
        "seed": 42,
        "ratios": {"train": 0.7, "val": 0.15, "test": 0.15},
        "participants": {"p01": "train", "p02": "train", "p03": "val"},
        "clip_counts": {"train": 4, "val": 1, "test": 0},
    }
    save_manifest(paths.manifests_dir, m)
    return settings


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


# ---- features ----


def test_normalize_is_scale_and_translation_invariant():
    rng = np.random.default_rng(0)
    seq = rng.normal(size=(12, 21, 3)) + np.array([100.0, -40.0, 5.0])
    moved = seq * 2.7 + np.array([500.0, 500.0, 0.0])
    a = normalize_landmarks(seq)
    b = normalize_landmarks(moved)
    np.testing.assert_allclose(a, b, atol=1e-9)
    # wrist is the origin of every frame
    np.testing.assert_allclose(a[:, 0, :], 0.0, atol=1e-12)


def test_resample_and_features_shapes_deterministic():
    rng = np.random.default_rng(1)
    seq = rng.normal(size=(9, 21, 3))
    assert resample(seq, SEQ_LEN).shape == (SEQ_LEN, 21, 3)
    f1 = sequence_to_features(seq)
    f2 = sequence_to_features(seq)
    assert f1.shape == (FEATURE_DIM,)
    assert np.array_equal(f1, f2)  # pure function, no randomness


def test_features_reject_too_short_sequences():
    seq = np.zeros((MIN_FRAMES - 1, 21, 3))
    with pytest.raises(ValueError, match=f"at least {MIN_FRAMES}"):
        sequence_to_features(seq)


# ---- baseline model ----


def _toy(n=20, d=6, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, d))
    y = np.array(["A" if i % 2 else "B" for i in range(n)])
    return X, y


def test_fit_is_seed_deterministic_and_separates_classes():
    X, y = _toy()
    m1 = LogisticBaseline(lr=0.5, epochs=25, seed=7)
    m2 = LogisticBaseline(lr=0.5, epochs=25, seed=7)
    losses1 = m1.fit(X, y)
    losses2 = m2.fit(X, y)
    assert losses1 == losses2  # same seed -> identical trajectory
    assert len(losses1) == 25
    preds = m1.predict(X)
    assert {p for p, _ in preds} <= {"A", "B"}
    assert all(0.0 <= c <= 1.0 for _, c in preds)
    probs = m1.predict_proba(X)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-9)


def test_predict_requires_training():
    with pytest.raises(BaselineNotTrained):
        LogisticBaseline().predict(np.zeros((2, 6)))


def test_save_load_roundtrip_identical(tmp_path):
    X, y = _toy()
    m = LogisticBaseline(epochs=15, seed=3)
    m.fit(X, y)
    path = tmp_path / "model.npz"
    m.save(path)
    loaded = LogisticBaseline.load(path)
    assert loaded.classes == m.classes
    np.testing.assert_allclose(loaded.predict_proba(X), m.predict_proba(X))


def test_onnx_matches_python_probabilities(tmp_path):
    ort = pytest.importorskip("onnxruntime")
    X, y = _toy()
    m = LogisticBaseline(epochs=20, seed=1)
    m.fit(X, y)
    path = tmp_path / "model.onnx"
    m.export_onnx(path)

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    assert inp.shape == [1, X.shape[1]]
    dtype = np.float32 if inp.type == "tensor(float)" else np.float64
    out = sess.run(None, {inp.name: X[:1].astype(dtype)})[0]
    np.testing.assert_allclose(out[0], m.predict_proba(X[:1])[0], atol=1e-4)


# ---- validation prechecks (manifest-level, no phantom work) ----


def test_validate_missing_dataset(settings):
    with pytest.raises(TrainingError, match="does not exist"):
        validate_request(settings, "nope")


def test_validate_requires_splits(settings):
    manifest_with(settings, "nosplits", [("p01", "WATER")], splits=None)
    with pytest.raises(TrainingError, match="No splits"):
        validate_request(settings, "nosplits")


def test_validate_requires_min_train_clips(settings):
    manifest_with(
        settings, "few", [("p01", "WATER"), ("p01", "FOOD")],
        splits={"participants": {"p01": "train"}},
    )
    with pytest.raises(TrainingError, match=f"at least {MIN_TRAIN_CLIPS}"):
        validate_request(settings, "few")


def test_validate_requires_min_classes(settings):
    clips = [("p01", "WATER"), ("p01", "WATER"), ("p02", "WATER"), ("p02", "WATER")]
    manifest_with(
        settings, "oneclass", clips,
        splits={"participants": {"p01": "train", "p02": "train"}},
    )
    with pytest.raises(TrainingError, match=f"at least {MIN_CLASSES}"):
        validate_request(settings, "oneclass")


def test_validate_returns_train_and_eval_clips(settings):
    manifest_with(
        settings, "ok",
        [("p01", "WATER"), ("p01", "FOOD"), ("p02", "WATER"), ("p02", "FOOD"), ("p03", "WATER")],
        splits={"participants": {"p01": "train", "p02": "train", "p03": "val"}},
    )
    train, eval_by_split = validate_request(settings, "ok")
    assert len(train) == 4
    assert len(eval_by_split["val"]) == 1
    assert eval_by_split["test"] == []


# ---- train_sign end-to-end (real decode, injected landmarks) ----


def test_train_sign_end_to_end(sign_dataset, tmp_path):
    progress: list[tuple[int, int, float]] = []

    def cb(epoch: int, total: int, loss: float) -> None:
        progress.append((epoch, total, loss))

    result = train_sign(
        settings=sign_dataset,
        dataset_id="default",
        seed=42,
        epochs=30,
        extractor=PatternExtractor(),
        progress_cb=cb,
    )

    assert result["labels"] == ["FOOD", "WATER"]
    assert result["preprocessing_version"] == "sign_v1"
    assert len(result["version"]) == 12
    ev = result["evaluation"]
    assert ev["train"]["accuracy"] >= 0.75          # real, computed
    assert ev["train"]["confusion_matrix"] == [[2, 0], [0, 2]]
    assert ev["train"]["per_class"] == {
        "FOOD": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 2},
        "WATER": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 2},
    }
    assert isinstance(ev["val"], dict) and "accuracy" in ev["val"]
    assert ev["test"] is None                        # honestly absent
    assert ev["clips_skipped"] == []

    # per-epoch progress actually happened
    assert len(progress) == 30
    assert all(total == 30 for _, total, _ in progress)

    out = sign_dataset.paths.models_dir / "sign"
    assert (out / "model.npz").is_file()
    assert (out / "model.onnx").is_file()
    on_disk = json.loads((out / "manifest.json").read_text())
    assert on_disk["version"] == result["version"]
    assert on_disk["input_shape"] == [1, FEATURE_DIM]


def test_train_sign_without_usable_clips_fails_honestly(sign_dataset):
    class NoHands:
        def extract(self, frame):
            return None

    with pytest.raises(TrainingError, match="hand not detected"):
        train_sign(settings=sign_dataset, dataset_id="default", extractor=NoHands())


# ---- training route worker (real rows, stubbed trainer) ----


def _stub_manifest() -> dict:
    return {
        "version": "stub00000001",
        "labels": ["FOOD", "WATER"],
        "evaluation": {
            "train": {"accuracy": 1.0, "macro_f1": 1.0, "confusion_matrix": [[2, 0], [0, 2]]},
            "val": {"accuracy": 1.0, "macro_f1": 1.0},
            "test": None,
            "clips_used": 4,
            "clips_skipped": [],
            "classes": ["FOOD", "WATER"],
            "final_loss": 0.1,
        },
    }


def _train_stub(**kwargs):
    cb = kwargs["progress_cb"]
    cb(1, 2, 0.9)
    cb(2, 2, 0.4)
    return _stub_manifest()


def test_route_worker_completes_with_real_logs(client, sign_dataset, monkeypatch):
    monkeypatch.setattr(training_route, "train_sign", _train_stub)
    r = client.post(
        "/api/v1/training/jobs",
        json={"modality": "sign", "dataset": "default", "config": {"epochs": 2}},
    )
    assert r.status_code == 201
    job_id = r.json()["job"]["id"]

    assert wait_for(
        lambda: client.get(f"/api/v1/training/jobs/{job_id}").json()["job"]["status"]
        in ("COMPLETED", "FAILED")
    )
    body = client.get(f"/api/v1/training/jobs/{job_id}").json()
    job = body["job"]
    assert job["status"] == "COMPLETED", job["error"]
    assert job["progress"] == 1.0
    assert job["metrics"]["version"] == "stub00000001"
    assert job["metrics"]["train_accuracy"] == 1.0
    lines = [entry["line"] for entry in body["logs"]]
    assert any(line.startswith("epoch 1/2 loss=") for line in lines)
    assert any(line.startswith("epoch 2/2 loss=") for line in lines)
    assert any(line.startswith("training started") for line in lines)
    assert any(line.startswith("exported sign model") for line in lines)

    # lock was released: a second job can be queued and finishes too
    r2 = client.post(
        "/api/v1/training/jobs",
        json={"modality": "sign", "dataset": "default", "config": {"epochs": 2}},
    )
    assert r2.status_code == 201
    job2 = r2.json()["job"]["id"]
    assert wait_for(
        lambda: client.get(f"/api/v1/training/jobs/{job2}").json()["job"]["status"]
        in ("COMPLETED", "FAILED")
    )
    assert client.get(f"/api/v1/training/jobs/{job2}").json()["job"]["status"] == "COMPLETED"


def test_route_rejects_while_lock_held(client):
    assert training_route._TRAINING_LOCK.acquire(blocking=False)
    try:
        r = client.post(
            "/api/v1/training/jobs", json={"modality": "sign", "dataset": "default"}
        )
        assert r.status_code == 409
        assert "already running" in r.json()["detail"]
        assert client.get("/api/v1/training/jobs").json() == []
    finally:
        training_route._TRAINING_LOCK.release()


def test_route_cancellation_observed_by_worker(client, sign_dataset, monkeypatch):
    def blocking_stub(**kwargs):
        cb = kwargs["progress_cb"]
        for i in range(1000):
            cb(min(i + 1, 2), 2, 0.5)
            time.sleep(0.02)
        raise AssertionError("worker was never cancelled")

    monkeypatch.setattr(training_route, "train_sign", blocking_stub)
    r = client.post(
        "/api/v1/training/jobs",
        json={"modality": "sign", "dataset": "default", "config": {"epochs": 2}},
    )
    assert r.status_code == 201
    job_id = r.json()["job"]["id"]

    assert wait_for(
        lambda: client.get(f"/api/v1/training/jobs/{job_id}").json()["job"]["status"]
        == "RUNNING"
    )
    cancelled = client.post(f"/api/v1/training/jobs/{job_id}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    assert wait_for(
        lambda: client.get(f"/api/v1/training/jobs/{job_id}").json()["job"]["status"]
        == "CANCELLED"
    )
    # worker released the lock on its way out
    assert wait_for(lambda: training_route._TRAINING_LOCK.acquire(blocking=False))
    training_route._TRAINING_LOCK.release()


def test_route_trainer_errors_become_failed_job(client, sign_dataset, monkeypatch):
    def failing_stub(**kwargs):
        raise TrainingError("Only 0 usable train clip(s) after landmark extraction")

    monkeypatch.setattr(training_route, "train_sign", failing_stub)
    r = client.post(
        "/api/v1/training/jobs", json={"modality": "sign", "dataset": "default"}
    )
    assert r.status_code == 201
    job_id = r.json()["job"]["id"]
    assert wait_for(
        lambda: client.get(f"/api/v1/training/jobs/{job_id}").json()["job"]["status"]
        == "FAILED"
    )
    job = client.get(f"/api/v1/training/jobs/{job_id}").json()["job"]
    assert "usable train clip" in job["error"]


def test_reconcile_marks_stale_jobs_failed(client):
    app = client.app.state.application
    job_id = app.db.create_job("sign", "default", {"epochs": 2})
    assert app.reconcile_stale_jobs() >= 1
    job = app.db.get_job(job_id)
    assert job["status"] == "FAILED"
    assert "restart" in job["error"]


def test_recognizer_builds_extractor_by_default(tmp_path):
    """The production recognizer must never be constructible without a
    landmark source: application.py builds it with only a model path, and a
    silent None extractor made predict_frame abstain forever."""
    from silentos.sign.landmarks import HandExtractor
    from silentos.sign.pipeline import SignRecognizer

    model = tmp_path / "models" / "sign" / "model.npz"
    model.parent.mkdir(parents=True)
    rec = SignRecognizer(model)
    assert isinstance(rec._extractor, HandExtractor)
    assert rec._extractor._model_path == tmp_path / "models" / "assets" / "hand_landmarker.task"

    sentinel = object()
    assert SignRecognizer(model, extractor=sentinel)._extractor is sentinel
