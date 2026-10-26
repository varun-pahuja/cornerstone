# Camera subsystem

Phase 3 of SilentOS. Everything in `backend/src/silentos/camera/` — common
provider interface, five concrete providers, and a capture manager with a
bounded latest-frame buffer.

## Providers

| Provider | Key | Source | Availability |
|---|---|---|---|
| `MockCameraProvider` | `mock` | Deterministic generated frames with a burned-in counter | Always. **Tests only** — never presented to users as a real camera |
| `VideoFileProvider` | `video_file` | Replays a clip from disk, loops at EOF | Any readable video file (configured via `camera.video_path`) |
| `DevelopmentWebcamProvider` | `development_webcam` | Laptop/USB webcam via V4L2 (`cv2.VideoCapture`) | Hosts with `/dev/video*` (verified on this machine: `/dev/video0`, `/dev/video1`) |
| `PiCameraProvider` | `pi_camera` | Raspberry Pi Camera Module via Picamera2 | Raspberry Pi only — raises `CameraUnavailable` elsewhere |
| `PiUsbWebcamProvider` | `pi_usb_webcam` | USB webcam on the Pi (V4L2 via cv2) | Any V4L2 device; guarded on non-Pi hosts |

Rules the providers follow:

- **Construction never touches hardware.** `build_provider()` only
  instantiates; `open()` acquires the device and raises `CameraUnavailable`
  (missing hardware/library) or `CameraError` (I/O failure) honestly.
- **Pi providers are guarded.** `/proc/device-tree/model` is checked before
  importing `picamera2`, so the same code runs on the laptop without
  pretending Pi hardware exists.
- **Status semantics.** Failed `open()` → `UNAVAILABLE` (missing hardware) or
  `ERROR` (device failure) with the real message in `error`. Mid-run read
  failure → `ERROR`, capture thread exits.

## Capture manager

`CameraManager` runs one daemon capture thread per active camera:

```
start(provider, kwargs)
  └─ open() ── spawn capture loop
        loop: read() → push to deque(maxlen=1) → throttle to target fps
stop() ── set stop event → join thread → close()
```

**Bounded frame buffer.** Frames land in a `collections.deque(maxlen=1)` — a
bounded queue that drops stale frames. Live recognition and preview only ever
need the freshest frame; older ones are evicted the moment a new one arrives,
and `frames_dropped` counts the evictions. There is deliberately no unbounded
queue anywhere on the capture path.

**Locking.** `_life` serializes start/stop; `_lock` guards state and the frame
buffer. The capture loop only takes `_lock`, so joining a thread never happens
while holding it.

## HTTP API

| Endpoint | Behavior |
|---|---|
| `GET /api/v1/cameras` | Source list: configured file, mock, laptop webcam (real `/dev/video*` probe), Pi sources (marked unavailable off-Pi) |
| `GET /api/v1/camera/status` | `DISCONNECTED / CONNECTING / CONNECTED / ERROR / UNAVAILABLE` + resolution, fps, `frames_captured`, `frames_dropped`, `last_frame_age_ms`, `error` |
| `POST /api/v1/camera/start` | Starts the configured provider; 503 with the real failure reason when it cannot open |
| `POST /api/v1/camera/stop` | Stops and releases the device |
| `POST /api/v1/camera/reconnect` | stop + start |
| `GET /api/v1/camera/frame.jpg` | Latest frame as JPEG (`X-Frame-Seq` header), `503` when no frame exists; `Cache-Control: no-store` |
| `GET /api/v1/camera/capabilities` | Kernel-reported V4L2 device names from `/sys/class/video4linux` |
| `GET/PUT /api/v1/camera/config` | Provider/resolution/fps/path/index; provider changes report `requires_restart` |

Preview transport: the dashboard polls `frame.jpg` at ~2.5 fps (bounded,
cheap). The recognition path reads `latest_frame()` in-process at full rate —
frames are never streamed over WebSocket.

## Deployment notes (Raspberry Pi)

- **Pi Camera Module:** install `python3-picamera2` (system package), enable
  the camera via `raspi-config`, verify with `libcamera-hello`. The provider
  checks `/proc/device-tree/model` first, so a laptop with picamera2 installed
  still reports `UNAVAILABLE` — correct, there is no module attached.
- **USB webcam:** `v4l2-ctl --list-devices` to confirm the node; set
  `camera.device_index` accordingly. USB cams on Pi draw extra current — use a
  powered hub for anything beyond a Pi Cam.
- **Multiple sources:** only one camera runs at a time (`CameraManager` is
  single-source by design).

## Tests

`backend/tests/test_camera.py` (16 tests): mock capture flow, bounded-buffer
invariant (drops counted, single packet held, freshest seq wins), video-file
looping at EOF (real MJPG file written by cv2), unknown provider rejection,
Pi-provider unavailability off-Pi, HTTP start/stop/status/frame round-trips,
honest 503s, and hardware tests that auto-skip when `/dev/video0` or
`/sys/class/video4linux` is absent. Verified live on this machine against the
physical webcam.
