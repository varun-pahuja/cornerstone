# SilentOS

Offline-first assistive communication: recognises **Indian Sign Language (ISL)
words** and **silent lip movements** from a camera, fuses the two modalities
with a confidence policy, and speaks/writes the result. No cloud services in
normal operation.

- **Backend** — Python 3.12+ / FastAPI, `backend/src/silentos/`: camera providers,
  MediaPipe landmark extraction, dataset engine, sign + lip pipelines, ONNX
  inference, fusion, speech, calibration, SQLite history.
- **Frontend** — React 19 + TypeScript + Vite, `frontend/`: Overview, Live Vision,
  AI Lab, Dataset Studio, Training Center, History, Calibration, Device Settings,
  System Health.
- **Target** — laptops (Linux/macOS/Windows), Raspberry Pi 4 (guide only, untested),
  and Google Colab for training when local landmark extraction is unavailable.

---

## 1. Honest status (2026-10-31)

| Area | State |
|---|---|
| Backend phases 1–9 | Code-complete, **105 tests passing** |
| Dashboard | Complete, frozen design |
| Real dataset | **128 ISL clips** (7 of 10 vocabulary classes), SHA-256 verified, participant-pinned splits — `docs/isl40_coverage.md` |
| Sign model | **Trained** `ae19271b2b19` — test accuracy **0.944** (3 unseen signers), macro-F1 0.808. Artifacts in `models/sign/` (gitignored), evidence in `docs/evidence/colab-run/` |
| Sign live recognition | **Not verified.** Live camera → fusion → dashboard has never run (blocked by local MediaPipe failure, `docs/evidence/t-ml-01-2026-10-30/`) |
| Lip model | **None.** Code exists but has audit blockers; no clips recorded — `docs/lip_phase.md` |
| Lip live recognition | **None** |
| Fusion | Unit-tested; untested with real models. Default config abstains single-modality predictions — see §9 |
| Missing vocabulary | PAIN, DOCTOR, TOILET (no usable source data; recording needed) |
| Raspberry Pi | Deployment guide written (`docs/deployment_raspberry_pi.md`); **never run on hardware** |

Accuracy figures above are measured on 18 held-out clips from 3 signers not seen
in training. They are not a claim about continuous live signing. Backend tests
validate code paths, not model accuracy.

## 2. Vocabulary

`HELP, WATER, FOOD, PAIN, YES, NO, STOP, DOCTOR, TOILET, THANK YOU`
(+ internal abstain output `PLEASE REPEAT`).

Single source of truth: `configs/default.yaml`. The trained model covers 7 of
these (`HELP, WATER, FOOD, YES, NO, STOP, THANK YOU`); the other three have no
data and are never predicted.

---

## 3. Requirements

| Component | Minimum | Verified on |
|---|---|---|
| Python | 3.12 | 3.14.8 (Arch Linux) |
| Node.js | 20 | 26.12.1 |
| Disk | ~1.5 GB (venv + models + data) | — |
| RAM | 4 GB | — |
| Camera | any V4L2/USB webcam or phone stream | none yet tested |
| GPU | **not required** | — |
| Speech output | optional `espeak-ng` on `PATH` | not installed in this env |

No GPU is needed for inference or training — the baseline is numpy/ONNX and the
sign model format is a single `(1, 2016) → (1, 7)` graph.

### Platform notes

- **Linux**: install `python3`, `python3-venv`, `nodejs`, `npm`; add `espeak-ng`
  if you want speech. Webcam access needs the user in the `video` group.
- **macOS**: `brew install python@3.12 node espeak-ng`. The first camera access
  triggers a TCC permission prompt for the terminal app.
- **Windows**: use PowerShell; activate the venv with
  `.venv\Scripts\Activate.ps1`. Camera backends differ (MediaPipe/OpenCV use
  Media Foundation). WSL2 has no camera access — use the Windows-side backend or
  a network/video-file source.
- **Raspberry Pi 4**: see `docs/deployment_raspberry_pi.md`; MediaPipe wheels for
  Pi are limited and **untested here**.
- **Colab**: use it for training only, not for the API server.

---

## 4. Clone and install the backend

```bash
git clone https://github.com/varun-pahuja/cornerstone.git
cd cornerstone

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -e "backend/[dev,inference,vision]"
```

What the extras add (`pyproject.toml`):

| Extra | Packages | Needed for |
|---|---|---|
| (base) | fastapi, uvicorn, pydantic, pyyaml, psutil, opencv-python-headless, numpy, python-multipart | API server, camera, dataset engine |
| `inference` | onnxruntime | running `.onnx` models |
| `vision` | mediapipe | landmark extraction (sign + lip) |
| `dev` | pytest, pytest-asyncio, httpx | tests |
| `training` | torch | **not used** by the current numpy baseline; install only if you add a torch model |

If you will train or export models, also install the ONNX exporter (it is imported
lazily and is not in any extra):

```bash
pip install onnx
```

Frontend:

```bash
cd frontend
npm ci
```

## 5. Configure

Configuration is YAML. The backend reads exactly one environment variable for
config: `SILENTOS_CONFIG` (path to a YAML file). Two more env vars are read
elsewhere: `SILENTOS_MEDIAPIPE_DELEGATE=cpu` (see §10) and no others — a `.env`
file is **not** auto-loaded.

```bash
export SILENTOS_CONFIG=./configs/development.yaml   # or configs/default.yaml
```

`configs/`:

| File | Use |
|---|---|
| `default.yaml` | production-ish defaults, `recognition.mode: both`, fusion thresholds 0.6 |
| `development.yaml` | debug logging, laptop video-file camera |
| `raspberry_pi.yaml` | Pi camera + reduced resolution |

Key sections to edit:

```yaml
camera:
  provider: video_file        # video_file | mock | development_webcam | pi_camera | pi_usb_webcam
  video_path: null            # required for video_file
  device_index: 0             # webcam index
recognition:
  mode: both                  # sign | lip | both
  inference_interval_ms: 200
fusion:
  sign_threshold: 0.6
  lip_threshold: 0.6
  allow_single_modality: false
output:
  speech_enabled: false       # needs espeak-ng
```

Camera providers are implemented in `backend/src/silentos/camera/providers.py`;
`pi_camera` requires `picamera2` on a Pi and raises a clear error elsewhere.
Start with `mock` or `video_file` on a machine without a camera.

## 6. Restore the trained model (fresh clone)

`models/` is gitignored, so a clone has **no model and no MediaPipe task files**.
Restore from the Colab Drive folder `SilentOS_artifacts/ae19271b2b19/` or from the
`silentos.zip` backup:

```bash
mkdir -p models/sign models/assets
cp <source>/model.npz <source>/model.onnx <source>/manifest.json models/sign/
cp <source>/hand_landmarker.task face_landmarker.task models/assets/   # or from a backup

sha256sum models/sign/*
# ae19271b2b1978e2b934085e40b37015a07dc512d6aa1db5df67788529699436  model.npz
# 95c2dea6f5e4317a46a1db814e905f418244755b657832818437b4dfec14df53  model.onnx
# ac3e092dd6e3aad2db0fd2256624b91522b497ba74fe35a796de27d2008a796a  manifest.json
```

These hashes identify the only verified artifact set. A mismatch means something
else — do not label it `ae19271b2b19`.

Quick loader + ONNX smoke test:

```bash
.venv/bin/python - <<'EOF'
import numpy as np, onnxruntime as ort, json
m = json.load(open("models/sign/manifest.json"))
print("version", m["version"], "labels", m["labels"])
s = ort.InferenceSession("models/sign/model.onnx")
x = np.zeros((1, 2016), np.float32)
p = s.run(None, {s.get_inputs()[0].name: x})[0]
print("shape", p.shape, "sum", float(p.sum()))
EOF
```

## 7. Run

Backend (keep this shell open):

```bash
source .venv/bin/activate
export SILENTOS_CONFIG=./configs/development.yaml
python -m uvicorn silentos.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

Verify:

```bash
curl -s localhost:8000/api/v1/health
curl -s localhost:8000/api/v1/status
curl -s localhost:8000/api/v1/models          # sign_status: LOADED / NOT_LOADED / NOT_TRAINED
curl -s localhost:8000/api/v1/recognition/status
```

Interactive API docs: `http://127.0.0.1:8000/docs`.

Frontend (second shell):

```bash
cd frontend
npm run dev        # http://localhost:5173, proxies /api → 127.0.0.1:8000
```

Production build:

```bash
cd frontend && npm run build     # → frontend/dist/
```

The backend has **no built-in static mount** for `frontend/dist/`. Serve the
built files with any static server (nginx, caddy, `python -m http.server`) and
reverse-proxy `/api/` to the backend on port 8000.

Speech output: install `espeak-ng`, set `output.speech_enabled: true`. Without
the binary the engine reports itself unavailable rather than lying.

## 8. Dataset

The 128 ISL clips are also gitignored. Re-ingest (needs network + Hugging Face
access):

```bash
.venv/bin/python scripts/ingest_isl.py
```

This is idempotent: it downloads the target classes, verifies SHA-256, registers
clips in `data/manifests/isl40.json`, and pins participants to splits. Provenance
and licences: `docs/isl40_coverage.md`.

Record your own clips in the dashboard: **Dataset Studio** → select camera →
choose modality (`sign` or `lip`) → label → participant id → record. Clips land
in `data/raw/` and are registered automatically.

## 9. Training

Two paths:

**A. Dashboard / API** — Training Center → pick dataset + modality → train. Jobs
run in the backend with a lock, logs, cancel, and crash reconciliation. Routes:
`POST /api/v1/training/jobs`, `GET /api/v1/training/jobs/{id}`.

**B. Colab (the path that actually produced the shipped model)** —
`training/notebooks/silentos_first_training.ipynb`. Upload `silentos.zip` (repo
without `.venv`/`.git`/`node_modules`), mount Drive, run. The notebook pins
`SILENTOS_MEDIAPIPE_DELEGATE=cpu` before importing `silentos`, gates on N
successful extractions, trains, evaluates on participant-held-out splits, and
writes artifacts + evidence to Drive. Copy `model.npz`, `model.onnx`,
`manifest.json` back into `models/sign/` and verify the hashes (§6).

Do not train on this laptop until §10 is resolved — extraction is killed by the
kernel here.

## 10. Known blocker: MediaPipe extraction is SIGKILLed locally

Symptom: `probe`/`extract` on `sign` or `lip` dies in ~1 s with no Python
traceback; exit status -9, kernel log shows a MediaPipe thread terminating. numpy,
onnxruntime and OpenCV loops run fine for 15 s; only MediaPipe dies.

Investigated (T-ML-01, `docs/evidence/t-ml-01-2026-10-30/FINDINGS.md`): no OOM
(`oom_kill 0`), no rlimits, no seccomp/BPF/AppArmor/security agent, no ptrace, no
userspace signal; both `cpu` and `gpu` delegates abort (GPU one after successful
EGL init). Kernel taint comes only from the NVIDIA out-of-tree module. Cause
remains host-specific and unresolved.

Consequences:

- Inference code is fine — the shipped model was verified end-to-end in Colab.
- Live recognition on this host is blocked until extraction survives here.
- `SILENTOS_MEDIAPIPE_DELEGATE=cpu` avoids the EGL abort path but does not stop the
  kill on this machine. On other machines, prefer `cpu` for headless/Colab.
- Training and dataset QC can be moved to Colab.

## 11. Tests and checks

```bash
.venv/bin/python -m pytest backend/tests -q        # 105 passed
cd frontend && npm run build                       # tsc -b && vite build
cd frontend && npm run lint                        # oxlint
```

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `sign predictions never appear` | Default config is `mode: both` + `allow_single_modality: false`, so with no lip model every sign-only decision is abstained. Set `recognition.mode: sign` or `fusion.allow_single_modality: true` (T-FUS-02) |
| `Address already in use` | Another uvicorn on :8000, or Vite on :5173; change `--port` / Vite port |
| `config file not found` | `SILENTOS_CONFIG` points at a missing file; use `./configs/development.yaml` |
| `Settings validation error` on YES/NO | Unquoted `YES`/`NO` are YAML 1.1 booleans — keep them quoted |
| MediaPipe import fails | Python 3.14 only has a tasks-only wheel here; MediaPipe still kills extraction (§10). Backend + model tests do not need it |
| `/api/v1/models` shows `sign_status: NOT_TRAINED` | `models/sign/` empty — restore §6 |
| No camera in `/api/v1/cameras` | `development_webcam` provider, correct `device_index`, user in `video` group |
| Speech silent | `espeak-ng` missing or `output.speech_enabled: false` |
| `ModuleNotFoundError: onnx` when training | `pip install onnx` (§4) |
| Slow startup | Startup reconciles stale training jobs and probes model files; normal |

## 13. Privacy

Everything is local: `data/`, `models/`, SQLite history. The API binds
`127.0.0.1` by default. No telemetry, no cloud calls in normal operation. The
Colab workflow sends your clip archive to Google by design — do that only for
data you are allowed to upload.

## 14. Documentation

| Doc | Contents |
|---|---|
| `TODO.md` | Central task registry (IDs, deps, acceptance, blockers) |
| `docs/implementation_status.md` | 30-area requirement audit |
| `docs/lip_phase.md` | Lip audit + dataset collection/evaluation plan |
| `docs/evidence/colab-run/REPORT.md` | Shipped model: run, metrics, limits, reproduction |
| `docs/evidence/t-ml-01-2026-10-30/FINDINGS.md` | Local MediaPipe SIGKILL investigation |
| `docs/architecture.md` | Architecture as built |
| `docs/isl40_coverage.md` | Dataset provenance, licences, split policy |
| `docs/datasets.md`, `docs/camera.md` | Dataset engine, camera providers |
| `docs/deployment_raspberry_pi.md` | Pi 4 deployment + systemd (untested) |
| `docs/PHASE_TODO.md` | Phase history |
| `docs/design_research.md` | Dashboard design record |
