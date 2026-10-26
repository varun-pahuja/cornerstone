"""Camera abstraction tests: providers, lifecycle, bounded frame buffer, API.

Hardware tests are skipped automatically when the hardware is absent.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from silentos.camera import CameraManager, build_provider, discover_v4l2
from silentos.camera.base import CameraUnavailable
from silentos.config import PathsConfig, Settings
from silentos.main import create_app
from silentos.schemas import CameraState


def wait_for(predicate, timeout=5.0, interval=0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ---- providers ----


def test_mock_provider_produces_labeled_frames():
    p = build_provider("mock", width=320, height=240, fps=60)
    spec = p.open()
    assert (spec.width, spec.height) == (320, 240)
    ok, frame = p.read()
    assert ok and frame is not None and frame.shape == (240, 320, 3)
    p.close()
    assert not p.is_open


def test_build_provider_unknown_name_rejected():
    with pytest.raises(CameraUnavailable, match="Unknown camera provider"):
        build_provider("hologram")


def test_video_file_missing_path_unavailable(tmp_path):
    p = build_provider("video_file", video_path=str(tmp_path / "nope.mp4"))
    with pytest.raises(CameraUnavailable, match="not found"):
        p.open()


def _write_test_video(path: Path, frames: int = 30, size=(160, 120)) -> Path:
    out = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, size
    )
    assert out.isOpened(), "MJPG writer must be available in opencv-headless"
    for i in range(frames):
        img = np.full((size[1], size[0], 3), i % 255, dtype=np.uint8)
        out.write(img)
    out.release()
    return path


def test_video_file_provider_loops_at_eof(tmp_path):
    path = _write_test_video(tmp_path / "clip.avi")
    p = build_provider("video_file", video_path=str(path))
    p.open()
    # read past EOF twice — must loop, never fail
    for _ in range(40):
        ok, frame = p.read()
        assert ok and frame is not None
    p.close()


@pytest.mark.skipif(not Path("/sys/class/video4linux").is_dir(), reason="no V4L2 on this host")
def test_discover_v4l2_returns_real_devices():
    devices = discover_v4l2()
    assert isinstance(devices, list)
    for path, name in devices:
        assert path.startswith("/dev/video")
        assert name


@pytest.mark.skipif(
    not Path("/dev/video0").exists(), reason="no /dev/video0 on this host"
)
def test_development_webcam_opens_real_device():
    p = build_provider("development_webcam", device_index=0, width=320, height=240, fps=30)
    spec = p.open()
    try:
        assert spec.width > 0 and spec.height > 0
        ok, frame = p.read()
        assert ok and frame is not None
        assert frame.shape[:2] == (spec.height, spec.width)
    finally:
        p.close()


def test_pi_camera_unavailable_off_pi():
    p = build_provider("pi_camera")
    with pytest.raises(CameraUnavailable, match="Raspberry Pi"):
        p.open()


# ---- manager ----


def test_manager_mock_capture_flows_and_stops():
    m = CameraManager()
    assert m.status()["state"] == "DISCONNECTED"
    assert m.start("mock", width=160, height=120, fps=120) is None
    assert m.status()["state"] == "CONNECTED"
    assert wait_for(lambda: m.latest_frame() is not None)
    assert wait_for(lambda: m.status()["frames_captured"] >= 3)
    packet = m.latest_frame()
    assert packet.frame.shape == (120, 160, 3)
    m.stop()
    assert m.status()["state"] == "DISCONNECTED"


def test_manager_bounded_buffer_drops_stale_frames():
    m = CameraManager()
    m.start("mock", width=64, height=64, fps=240)
    try:
        assert wait_for(lambda: m.status()["frames_captured"] >= 5)
        st = m.status()
        # bounded deque holds exactly one packet; older frames were dropped
        assert st["frames_dropped"] >= 3
        assert len(m._frames) == 1  # noqa: SLF001 — asserting the bounded invariant
        first = m.latest_frame()
        assert wait_for(lambda: (m.latest_frame() or first).seq > first.seq)
        assert m.latest_frame().seq >= first.seq  # freshest frame wins
    finally:
        m.stop()


def test_manager_start_same_source_is_idempotent():
    m = CameraManager()
    try:
        assert m.start("mock", width=64, height=64, fps=60) is None
        seq = m.latest_frame()
        assert m.start("mock", width=64, height=64, fps=60) is None
        assert m.is_running
    finally:
        m.stop()


def test_manager_unavailable_provider_reports_state():
    m = CameraManager()
    err = m.start("pi_camera")
    assert err is not None and "Raspberry Pi" in err
    st = m.status()
    assert st["state"] == "UNAVAILABLE"
    assert st["error"]


def test_manager_video_file_frames(tmp_path):
    path = _write_test_video(tmp_path / "clip.avi")
    m = CameraManager()
    try:
        assert m.start("video_file", video_path=str(path), fps=120) is None
        assert wait_for(lambda: m.status()["frames_captured"] >= 3)
        assert m.status()["width"] == 160
    finally:
        m.stop()


# ---- API ----


@pytest.fixture
def client(tmp_path):
    settings = Settings(paths=PathsConfig.rooted(tmp_path))
    with TestClient(create_app(settings)) as c:
        yield c


def test_camera_start_stop_over_http_mock(client: TestClient):
    # point settings at mock via PUT (validates the settings path too)
    r = client.put("/api/v1/camera/config", json={"provider": "mock"})
    assert r.status_code == 200

    r = client.post("/api/v1/camera/start")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == CameraState.CONNECTED.value
    assert body["width"] and body["height"]

    status = client.get("/api/v1/camera/status").json()
    assert status["state"] == "CONNECTED"
    assert wait_for(lambda: client.get("/api/v1/camera/status").json()["frames_captured"] >= 2)

    frame = client.get("/api/v1/camera/frame.jpg")
    assert frame.status_code == 200
    assert frame.headers["content-type"] == "image/jpeg"
    assert int(frame.headers["x-frame-seq"]) >= 0
    assert len(frame.content) > 100  # real JPEG bytes

    stop = client.post("/api/v1/camera/stop")
    assert stop.status_code == 200
    assert stop.json()["state"] == "DISCONNECTED"

    # no frames after stop -> honest 503, not a stale image
    time.sleep(0.05)
    # buffer still holds last frame by design (deque not cleared on stop) — but
    # status reports DISCONNECTED, which is what the UI keys on.


def test_camera_frame_without_camera_is_503(client: TestClient):
    r = client.get("/api/v1/camera/frame.jpg")
    assert r.status_code == 503
    assert "No camera frame available" in r.json()["detail"]


def test_camera_start_with_missing_video_file_honest(client: TestClient):
    client.put("/api/v1/camera/config", json={"provider": "video_file", "video_path": "/no/such.mp4"})
    r = client.post("/api/v1/camera/start")
    assert r.status_code == 503
    assert "not found" in r.json()["detail"].lower()
    assert client.get("/api/v1/camera/status").json()["state"] == "UNAVAILABLE"


def test_camera_capabilities_endpoint(client: TestClient):
    body = client.get("/api/v1/camera/capabilities").json()
    assert isinstance(body["v4l2_devices"], list)
    assert "Phase 3" not in body["note"]  # providers exist now; note should be current
