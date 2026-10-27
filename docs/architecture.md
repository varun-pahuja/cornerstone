# SilentOS — Architecture

Status: **Phases 1–8 complete; Phase 5 sign training live + Phase 6 silent-lip training live + Phase 7 live recognition runtime wired + Phase 8 speech output (`SpeechEngine` speaks accepted fused labels when enabled, honest espeak-ng unavailable detection). Calibration/deploy is Phase 9. 98 backend tests passing.** This document describes the architecture as
built; sections marked *planned* are designed but not yet implemented. Last updated:
2026-10-27.

## System overview

```
React + TypeScript + Vite dashboard          (frontend/)
        │  REST  /api/v1/*   (dev: Vite proxy → 127.0.0.1:8000)
        │  WebSocket /ws     (planned — bounded typed events)
        ▼
Python FastAPI backend                       (backend/src/silentos/)
        │  Application controller (state owner, no model execution in handlers)
        ├── SQLite  (settings, recognition history, training jobs)
        ├── Camera providers        (camera/)      [Phase 3]
        ├── Sign features+training  (sign/)        [Phase 5]
        ├── Mouth preprocessing     (lip/)         [Phase 6]
        ├── Sign + Lip inference     (recognition/) [Phase 5/6, runtime wiring pending]
        ├── Confidence fusion        (fusion/)      [Phase 7]
        └── Text/speech output       (output/)      [Phase 8]
        ▼
Local files only: data/, models/   — no cloud services in normal operation
```

Core principle: **the dashboard never runs AI models.** The Python backend is the single
source of truth for runtime state, camera status, model status, recognition results and
settings; recognition keeps running if the browser closes.

## Backend (`backend/src/silentos/`)

| Module | Status | Responsibility |
|---|---|---|
| `config.py` | ✅ | Pydantic settings loaded from `configs/*.yaml`; validation rejects bad thresholds/providers/vocabularies; `PathsConfig.rooted()` isolates test paths. |
| `schemas.py` | ✅ | All API contracts (Pydantic): runtime/camera/model state enums, `AppStatus`, `SystemMetrics`, `FusionDecision`, `ModalityPrediction`, `RecognitionEvent`, WS envelope (`schema_version 1.0`). |
| `database.py` | ✅ | SQLite (thread-safe, lock-guarded): settings KV, bounded recognition history with retention/max-entries pruning, training job records + log tailing. |
| `application.py` | ✅ | Central controller: owns real runtime state, builds `AppStatus`, collects **real** metrics via psutil (CPU, memory, disk, temperature when exposed; `null` → "Unavailable"). |
| `api/routes/health.py` | ✅ | `GET /api/v1/health` (no model loading), `GET /api/v1/status`, `GET /api/v1/system/metrics`. |
| `main.py` | ✅ | App factory `create_app()`, CORS for the dev origin, lifespan logging, `uvicorn silentos.main:app`; loads persisted settings overrides on startup. |
| `camera/` | ✅ | Provider interface + 5 providers (mock, video_file, development_webcam, pi_camera, pi_usb_webcam), guarded Pi imports, `CameraManager` capture thread with bounded `deque(maxlen=1)` latest-frame buffer (stale frames dropped, `frames_dropped` counted). Live-verified against the physical webcam. See `docs/camera.md`. |
| `dataset/` | ✅ | Validation (decode, duration 0.2–30 s, vocabulary, safe names), SHA-256 manifests, deterministic participant-based splits (no cross-split leakage, n<3 → train+warning), record-from-camera (bounded-buffer reads), multipart import, register-in-root, zip export. See `docs/datasets.md`. |
| `registry.py` | ✅ | Model manifest scan shared by `/models` and `app_status` — status derived from artifacts on disk (NOT_TRAINED / ERROR / NOT_LOADED), never assumed. |
| `sign/` | ✅ | Phase 5: MediaPipe `HandExtractor` (guarded imports, VIDEO-mode timestamps), wrist-relative + scale-invariant features (2016-dim, 32-frame resample), seed-deterministic `LogisticBaseline` (npz + ONNX export `(X−μ)/σ`, parity-tested), `train_sign` with honest per-split evaluation, `validate_request` shared precheck, `SignRecognizer` buffer. |
| `api/routes/training.py` | ✅ | Phase 5/6 job API: strict config validation (400, allowed keys `seed,epochs,lr,l2`), one-job lock (409), sign+lip both wired, dataset precheck **before** any row exists (409 + "No job was created."), 201 `{job}` create, daemon worker with per-epoch progress + `{ts,line}` logs, user cancellation observed per epoch, trainer failures stored as FAILED errors, flat metrics JSON; `Application.reconcile_stale_jobs()` runs at startup (stale QUEUED/RUNNING → FAILED "Interrupted by process restart"). |
| `api/routes/{settings,models,recognition,camera,datasets,diagnostics}.py` | ✅ | Phase 2 endpoints: validated settings PUT with persisted overrides + restart reporting; honest model status; history CRUD; real V4L2 discovery (`/sys/class/video4linux`); dataset stats counted from disk; runtime dependency probes. |
| `sign/` | ✅ | Phase 5: MediaPipe `HandExtractor` (guarded imports, VIDEO-mode timestamps), wrist-relative + scale-invariant features (2016-dim, 32-frame resample), seed-deterministic `LogisticBaseline` (npz + ONNX export `(X−μ)/σ`, parity-tested), `train_sign` with honest per-split evaluation, `validate_request` shared precheck, `SignRecognizer` buffer. |
| `lip/` | ✅ | Phase 6: MediaPipe `FaceLandmarker` (guarded imports), lip features (478×3 → normalized 32-frame, 45888-dim), seed-deterministic `LogisticBaseline` (npz + ONNX), `train_lip` with honest evaluation, `LipRecognizer` buffer. |
| `fusion/` | ✅ | Phase 7: `FusionEngine` + `fuse_predictions` (weighted confidence, agreement boost, abstain below `min_confidence`), `FusionPolicy`/`FusionWeights`. |
| `output/` | ✅ | Phase 8: `SpeechEngine` (espeak-ng wrapper, cooldown, thread-safe) + `speak_decision`; wired into recognition loop; honest unavailable detection. |
| recognition runtime, calibration | 🚧 planned Phase 9 | Live loop + speech wired; calibration/deploy pending. |

Security as built: binds `127.0.0.1` by default; no shell-execution endpoints; filesystem
access will be restricted to configured directories (validated identifiers, not raw paths).

## Frontend (`frontend/`)

| Piece | Status | Notes |
|---|---|---|
| Stack | ✅ | React 19, Vite 8, TypeScript 6 (strict, `erasableSyntaxOnly`), Tailwind CSS 4 (token theme), react-router 7, lucide-react, recharts (real training curves from job logs). |
| Design system | ✅ | "Obsidian Instrument" (dark, Newsreader + IBM Plex, single teal accent) tokens in `styles/globals.css`; fonts bundled offline; shadcn (base-nova) installed. Research + integration record: `docs/design_research.md`. |
| App shell | ✅ | Grouped nav (Console / Intelligence / System) with active indicator, top bar (breadcrumb + runtime badge + host), responsive icon rail < `lg`, connection footer polling `/health` every 10 s, global Toaster/TooltipProvider. |
| Typed API client | ✅ | `services/api.ts` — single fetch boundary, 10 s timeout, typed `ApiError`. |
| Pages | ✅ | All 9 redesigned: Overview (runtime/camera/recognition/readiness/meters/recent), Live Vision (preview + honest recognition lanes + timeline + side rail), AI Lab (real evaluation metrics + confusion matrices), Training Center (job list, epoch stepper, log-driven loss curves, dataset picker), Dataset Studio (disk-counted stats + record/import/validate/splits), History (paginated DB rows + clear), Calibration (honest "not implemented" + config defaults), Device Settings (validated PUT + restart banner), System Health (metrics + dependency probes). Verified via Playwright at 1920/1280/1024/390. |
| Live events | 🚧 | WebSocket client planned with the backend WS endpoint (bounded queue, reconnect). |

## Data flow (planned, Phase 3+)

```
Selected camera provider → single capture manager → frame validation/timestamps
    → bounded frame queues (drop-oldest; capture never blocks)
        → sign pipeline ─┐
        → lip pipeline  ─┴→ fusion (deterministic, threshold rules)
                              → accepted text → history + optional speech
                              → abstained    → "Please repeat."
```

One physical camera, one capture owner; both modalities share the same frames.

## Vocabulary

Single canonical list in `configs/default.yaml` (`HELP, WATER, FOOD, PAIN, YES, NO, STOP,
DOCTOR, TOILET, THANK YOU`) + internal abstain label `PLEASE REPEAT`. The same list feeds
labelling, training, inference, fusion and the dashboard; validation enforces uniqueness.

## Testing

- Backend: pytest (`.venv`), `backend/tests/` — currently 5 passing tests covering health,
  status honesty (no fabricated values), metrics reality, settings validation, config errors.
- Frontend: `tsc -b` type-check + `oxlint` clean + `vite build` all pass.
- Integration/hardware tests: planned (Phases 3+); hardware tests will be a separate suite.

## Deployment (planned, Phase 9)

Production: FastAPI serves the built frontend as static files from the same origin (no
CORS), systemd units for the API + edge runtime, camera providers switchable in
`configs/raspberry_pi.yaml`. Training runs in a separate process from live inference.
