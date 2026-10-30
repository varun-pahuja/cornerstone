# SilentOS

Local-first communication assistant that recognises **Indian Sign Language (ISL)
word-level gestures** and silent lip movements from a camera, fuses both
modalities, and speaks/writes the result — all on-device, no cloud.

- **Backend:** Python / FastAPI (`backend/src/silentos/`) — camera providers,
  dataset engine, sign + lip ML pipelines, confidence fusion, speech, calibration.
- **Frontend:** React + TypeScript + Vite (`frontend/`) — the "Obsidian Instrument"
  dashboard (Overview, Live Vision, AI Lab, Dataset Studio, Training Center,
  History, Calibration, Device Settings, System Health).
- **Target hardware:** Raspberry Pi 4 (4 GB), offline after setup.

## Honest status (2026-10-30)

| Area | State |
|---|---|
| Phases 1–9 (foundation → calibration + Pi guide) | **Code-complete**, 104 backend tests passing |
| Dashboard redesign | **Complete and frozen** |
| Real dataset | **128 ISL clips ingested** (7 of 10 vocabulary classes), SHA-256 verified, participant-held-out splits (`docs/isl40_coverage.md`) |
| Trained model | **None yet.** `models/sign/` and `models/lip/` are empty. |
| Blocker | Landmark extraction is killed (external SIGKILL, ~3 s) on the dev machine — evidence: `docs/evidence/t-ml-01-2026-10-30/`. First genuine training attempt runs on Google Colab: `training/notebooks/silentos_first_training.ipynb`. |
| Missing classes | PAIN, DOCTOR, TOILET are absent from the current dataset (local recording needed — no ASL substitutes). |
| Raspberry Pi | Deployment guide written (`docs/deployment_raspberry_pi.md`); **no hardware verification yet**. |

Backend tests validate *code paths*, not model accuracy. No accuracy, precision,
recall or F1 numbers exist yet because no real model has been trained.

## Vocabulary

`HELP, WATER, FOOD, PAIN, YES, NO, STOP, DOCTOR, TOILET, THANK YOU`
(+ internal abstain label `PLEASE REPEAT`). Single source of truth:
`configs/default.yaml`.

## Quickstart (development)

```bash
# Backend
python -m venv .venv
.venv/bin/pip install -e backend/
.venv/bin/python -m uvicorn silentos.main:app --app-dir backend/src --reload

# Frontend (separate shell)
cd frontend && npm ci && npm run dev   # proxies /api/v1 to 127.0.0.1:8000

# Tests
.venv/bin/python -m pytest backend/tests -q     # 104 passed
cd frontend && npx tsc -b && npx oxlint src && npm run build
```

Dataset (idempotent, downloads target classes from Hugging Face, verifies
SHA-256, registers, splits):

```bash
.venv/bin/python scripts/ingest_isl.py
```

## Documentation

| Doc | Contents |
|---|---|
| `TODO.md` | **Central task registry** (IDs, dependencies, acceptance, blockers) |
| `docs/implementation_status.md` | 30-area requirement audit |
| `docs/architecture.md` | System architecture as built |
| `docs/PHASE_TODO.md` | Phase history checklist |
| `docs/isl40_coverage.md` | Dataset provenance, licenses, split policy |
| `docs/camera.md`, `docs/datasets.md` | Camera providers, dataset engine |
| `docs/deployment_raspberry_pi.md` | Pi 4 deployment + systemd |
| `docs/design_research.md` | Dashboard design research record |
| `docs/skills_inventory.md` | Agent skills used on this project |

## Privacy

Local files only (`data/`, `models/`, SQLite). No cloud services in normal
operation; the API binds `127.0.0.1` by default.
