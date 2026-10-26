"""Camera discovery, status and configuration.

Discovery is real (reads /sys/class/video4linux); the capture runtime itself
arrives in Phase 3 — start/stop report that honestly instead of pretending.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...camera import discover_v4l2
from ...schemas import CameraConfigUpdate, CameraInfo, CameraStatus, CameraState, SettingsView
from ..deps import AppDep

# Spec §8.2: list lives at /cameras, everything else under /camera/*
router = APIRouter(prefix="/api/v1", tags=["camera"])

def _v4l2_devices() -> list[tuple[str, str]]:
    return discover_v4l2()


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


@router.get("/camera/status", response_model=CameraStatus)
def camera_status(app: AppDep) -> CameraStatus:
    st = app.camera.status()
    return CameraStatus(
        state=CameraState(st["state"]),
        provider=st["provider"] or app.settings.camera.provider,
        width=st["width"],
        height=st["height"],
        fps=st["fps"],
        frames_captured=st["frames_captured"],
        frames_dropped=st["frames_dropped"],
        last_frame_age_ms=st["last_frame_age_ms"],
        error=st["error"],
    )


@router.get("/camera/frame.jpg")
def camera_frame(app: AppDep):
    """Latest captured frame as JPEG. 503 while no camera is producing frames."""
    import cv2

    from fastapi import Response

    packet = app.camera.latest_frame()
    if packet is None:
        raise HTTPException(status_code=503, detail="No camera frame available yet")
    ok, buf = cv2.imencode(".jpg", packet.frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Frame JPEG encoding failed")
    return Response(
        content=buf.tobytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Frame-Seq": str(packet.seq)},
    )


@router.get("/camera/capabilities")
def capabilities(app: AppDep) -> dict:
    devices = _v4l2_devices()
    return {
        "v4l2_devices": [{"device_path": p, "name": n} for p, n in devices],
        "note": (
            "Kernel-reported device names from /sys/class/video4linux. "
            "Per-device format/framerate probing is not implemented — the "
            "provider negotiates resolution at open time instead."
        ),
    }


@router.get("/camera/config", response_model=SettingsView)
def get_config(app: AppDep) -> SettingsView:
    return SettingsView(**app.settings_view())


@router.put("/camera/config", response_model=SettingsView)
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


@router.post("/camera/start")
def start_camera(app: AppDep) -> dict:
    detail = app.start_camera()
    if detail is not None:
        # Real failure: unavailable hardware, missing file, device busy, ...
        raise HTTPException(status_code=503, detail=detail)
    return app.camera.status()


@router.post("/camera/stop")
def stop_camera(app: AppDep) -> dict:
    app.stop_camera()
    return app.camera.status()


@router.post("/camera/reconnect")
def reconnect_camera(app: AppDep) -> dict:
    app.stop_camera()
    detail = app.start_camera()
    if detail is not None:
        raise HTTPException(status_code=503, detail=detail)
    return app.camera.status()
