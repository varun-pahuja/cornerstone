# SilentOS — Raspberry Pi 4 Deployment (Phase 9)

Target: **Raspberry Pi 4 Model B (4 GB)**, Arch Linux ARM (aarch64) or Raspberry Pi OS
(Bullseye/Bookworm, 64-bit). Fully offline after initial setup — no network calls at
runtime.

## 1. System prerequisites

```bash
# Arch Linux ARM
sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm python python-pip ffmpeg v4l-utils espeak-ng
```

`espeak-ng` enables offline speech output (Phase 8). If skipped, the backend reports
speech unavailable honestly and recognition still works.

## 2. Python environment

```bash
cd /home/pi/silentos
python -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e backend/          # installs fastapi, uvicorn, mediapipe, opencv, etc.
```

> MediaPipe and OpenCV wheels for aarch64 are available on PyPI for Python 3.10–3.12.
> If your Pi image ships a newer Python, build may fall back to source — prefer
> Raspberry Pi OS Bookworm (Python 3.11) for prebuilt wheels.

## 3. Model assets

Copy the bundled MediaPipe task files (or download once while online):

```bash
mkdir -p models/assets
cp /path/to/hand_landmarker.task models/assets/
cp /path/to/face_landmarker.task models/assets/
```

Trained sign/lip models (from Training Center exports) go under:

```
models/sign/model.npz + manifest.json + model.onnx
models/lip/model.npz  + manifest.json + model.onnx
```

## 4. Camera

Enable the legacy camera stack if using the Pi Camera Module (not USB):

```bash
sudo raspi-config
# Interface Options → Camera → Enable
```

Verify a USB webcam is detected:

```bash
v4l2-ctl --list-devices
ls /dev/video*
```

Set `camera.provider` in `configs/raspberry_pi.yaml` (or via the dashboard's
Device Settings) to `pi_camera` (CSI) or `pi_usb_webcam` (USB).

## 5. Run

```bash
# Development
.venv/bin/python -m uvicorn silentos.main:app \
    --app-dir backend/src \
    --host 0.0.0.0 --port 8000

# Production (systemd, see below)
sudo systemctl enable --now silentos
```

Bind to `0.0.0.0` only on a trusted LAN; the API has no auth. For field use, keep it
on `127.0.0.1` and access via SSH tunnel, or put it behind a reverse proxy with auth.

## 6. systemd unit (optional)

`/etc/systemd/system/silentos.service`:

```ini
[Unit]
Description=SilentOS API
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/silentos
ExecStart=/home/pi/silentos/.venv/bin/python -m uvicorn silentos.main:app \
    --app-dir backend/src --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 7. Frontend (optional kiosk)

Build the dashboard on a dev machine and copy `frontend/dist/` to the Pi, or build
in place:

```bash
cd frontend && npm ci && npm run build
# serve dist/ via the same uvicorn process or a static file server
```

For a headless kiosk, point Chromium (on the Pi's display) at
`http://localhost:8000/` in `--kiosk` mode.

## 8. Offline verification

After setup, disconnect from the network and verify:

```bash
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v1/system/dependencies
```

All core dependencies (FastAPI, OpenCV, NumPy, MediaPipe) should report `available: true`.
`espeak-ng` shows `available: true` only if installed. No network egress is required at
runtime — recognition, training, and speech are fully local.
