# SilentOS — Architecture

Status: **Phase 1 (foundation) implemented.** This document describes the architecture as
built; sections marked *planned* are designed but not yet implemented. Last updated:
2026-10-26.

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
        ├── Hand/mouth preprocessing (preprocessing/) [Phase 5/6]
        ├── Sign + Lip inference     (recognition/) [Phase 5/6]
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
| `main.py` | ✅ | App factory `create_app()`, CORS for the dev origin, lifespan logging, `uvicorn silentos.main:app`. |
| camera, preprocessing, recognition, fusion, output, dataset, training | 🚧 planned Phases 3–8 | |

Security as built: binds `127.0.0.1` by default; no shell-execution endpoints; filesystem
access will be restricted to configured directories (validated identifiers, not raw paths).

## Frontend (`frontend/`)

| Piece | Status | Notes |
|---|---|---|
| Stack | ✅ | React 19, Vite 8, TypeScript 6 (strict, `erasableSyntaxOnly`), Tailwind CSS 4 (token theme), react-router 7, lucide-react, recharts (installed, awaiting real data). |
| Design system | ✅ | "Industrial Utilitarian" tokens in `styles/globals.css` (`@theme`); components use token utilities only. Research: `docs/design_research.md`. |
| App shell | ✅ | Dark nav rail with 9 routes, active-page indicator, responsive (icon-only < `md`), connection pill polling `/health` every 10 s. |
| Typed API client | ✅ | `services/api.ts` — single fetch boundary, 10 s timeout, typed `ApiError`. |
| Pages | 🚧 | `Overview` is wired to real `/status` + `/system/metrics` (loading/error/Unavailable states). The other 8 routes render explicit phase-labelled placeholders — no fake data or dead controls (Phase 2 builds them). |
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
