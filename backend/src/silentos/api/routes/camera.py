"""Camera discovery, status and configuration.

Discovery is real (reads /sys/class/video4linux); the capture runtime itself
arrives in Phase 3 — start/stop report that honestly instead of pretending.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...schemas import CameraConfigUpdate, CameraInfo, CameraStatus, CameraState, SettingsView
from ..deps import AppDep

router = APIRouter(prefix="/api/v1/camera", tags=["camera"])

_SYS_VIDEO = Path("/sys/class/video4linux")


def _v4l2_devices() -> list[tuple[str, str]]:
    """Return [(device_path, name)] for real V4L2 nodes, empty when absent."""
    if not _SYS_VIDEO.is_dir():
        return []
    devices: list[tuple[str, str]] = []
    for entry in sorted(_SYS_VIDEO.iterdir()):
        name_file = entry / "name"
        name = name_file.read_text().strip() if name_file.exists() else entry.name
        devices.append((f"/dev/{entry.name}", name))
    return devices


@router.get("/cameras", response_model=list[CameraInfo])
def cameras(app: AppDep) -> list[CameraInfo]:
    cfg = app.settings.camera
    devices = _v4l2_devices()
    out: list[CameraInfo] = []

    out.append(
        CameraInfo(
            provider="video_file",
            label="Video file" + (f" — {cfg.video_path}" if cfg.video_path else " (select a clip)"),
            device_path=cfg.video_path,
            available=True,
        )
    )
    out.append(
        CameraInfo(
            provider="mock",
            label="Mock source (deterministic test frames)",
            available=True,
            detail="For automated tests only; never presented as a live camera",
        )
    )
    out.append(
        CameraInfo(
            provider="development_webcam",
            label="Laptop webcam (development)"
            if devices
            else "Laptop webcam (development) — no devices found",
            device_path=devices[0][0] if devices else None,
            available=bool(devices),
            detail=None if devices else "No /dev/video* nodes detected",
        )
    )
    out.append(
        CameraInfo(
            provider="pi_camera",
            label="Raspberry Pi Camera Module",
            available=False,
            detail="Raspberry Pi hardware not present — implement + verify in Phase 10",
        )
    )
    out.append(
        CameraInfo(
            provider="pi_usb_webcam",
            label="USB webcam connected to the Raspberry Pi",
            available=False,
            detail="Raspberry Pi hardware not present — provider arrives in Phase 3",
        )
    )
    return out


@router.get("/status", response_model=CameraStatus)
def camera_status(app: AppDep) -> CameraStatus:
    st = app.app_status()
    return CameraStatus(
        state=CameraState.DISCONNECTED,
        provider=st.camera_provider,
        width=None,
        height=None,
        fps=None,
        frames_captured=0,
        last_frame_age_ms=None,
        error=None,
    )


@router.get("/capabilities")
def capabilities(app: AppDep) -> dict:
    devices = _v4l2_devices()
    return {
        "v4l2_devices": [{"device_path": p, "name": n} for p, n in devices],
        "note": (
            "Detailed format/framerate probing arrives with the camera "
            "providers (Phase 3); only kernel-reported device names are shown."
        ),
    }


@router.get("/config", response_model=SettingsView)
def get_config(app: AppDep) -> SettingsView:
    return SettingsView(**app.settings_view())


@router.put("/config", response_model=SettingsView)
def update_config(app: AppDep, update: CameraConfigUpdate) -> SettingsView:
    payload = update.model_dump(exclude_none=True)
    allowed = {
        "provider": "camera_provider",
        "target_width": "camera_target_width",
        "target_height": "camera_target_height",
        "target_fps": "camera_target_fps",
        "video_path": "camera_video_path",
        "device_index": "camera_device_index",
    }
    mapped = {allowed[k]: v for k, v in payload.items() if k in allowed}
    # Reject unknown provider names rather than storing them.
    if "camera_provider" in mapped and mapped["camera_provider"] not in {
        "video_file", "mock", "development_webcam", "pi_camera", "pi_usb_webcam"
    }:
        raise HTTPException(status_code=422, detail=f"Unknown provider: {mapped['camera_provider']}")
    return SettingsView(**app.apply_settings(mapped))


@router.post("/start")
def start_camera(app: AppDep) -> dict:
    raise HTTPException(
        status_code=503,
        detail="Camera runtime not implemented yet (arrives in Phase 3). No camera was opened.",
    )


@router.post("/stop")
def stop_camera(app: AppDep) -> dict:
    return {"state": CameraState.DISCONNECTED.value, "detail": "Camera was not running"}


@router.post("/reconnect")
def reconnect_camera(app: AppDep) -> dict:
    raise HTTPException(
        status_code=503,
        detail="Camera runtime not implemented yet (arrives in Phase 3).",
    )
