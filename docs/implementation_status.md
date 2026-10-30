# SilentOS — Implementation Status (requirement-by-requirement audit)

Audited: 2026-10-30, against the working tree at commit `2a0eb15` (phase 8) **plus
uncommitted Phase 9/10 work**. Every status below was checked against actual files,
tests run today, or a live probe — not against prior progress reports.

**Status legend:** COMPLETE (implemented + verified here) · PARTIAL (implemented,
requirements remain) · IN_PROGRESS · NOT_STARTED · BLOCKED (concrete dependency) ·
UNVERIFIED (exists, insufficient verification).

**Baseline note:** the original master prompt is not stored in-repo; the audit baseline
is `docs/PHASE_TODO.md` (phases 1–10) plus the 30 areas required by the audit request.

---

## 1–5. Foundation, backend, API, frontend, dashboard

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 1 | Repository foundation | **COMPLETE** | `pyproject.toml`, `configs/{default,development,raspberry_pi}.yaml`, `.env.example`, SQLite schema, git history through phase 8; `README.md` rewritten 2026-10-30 (was stale `# cornerstone`); `configs/default.yaml` YES/NO boolean bug fixed + regression test | — |
| 2 | Backend architecture | **COMPLETE** | `backend/src/silentos/` module set matches `docs/architecture.md`; Application controller, config, database, registry all present | — |
| 3 | API implementation | **COMPLETE** | Routes: health/status/metrics, settings, models, recognition, camera, datasets, diagnostics, training, **calibration (uncommitted, wired in `main.py`)**; 104 tests pass incl. 26 API tests | — |
| 4 | Frontend architecture | **COMPLETE** | React 19 + Vite + TS strict; `tsc -b` = 0, `oxlint` = 0 errors (2 warnings), `vite build` succeeds — all run today | chunk-size build warning (cosmetic) |
| 5 | Dashboard redesign | **COMPLETE** | All 9 pages + AppShell + design tokens (`frontend/src/styles/globals.css`) present; build green today. Historic Playwright verification at 1920/1280/1024/390 per PHASE_TODO (not re-run today). **Frozen by directive — do not redesign.** | — |

## 6–9. Camera subsystem

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 6 | Camera abstraction | **COMPLETE** | `camera/base.py`, `providers.py` (Mock, VideoFile, DevelopmentWebcam, PiUsbWebcam, PiCamera + registry), `manager.py` bounded buffer; 16 camera tests pass | — |
| 7 | Raspberry Pi camera (CSI) | **PARTIAL** | `PiCameraProvider` implemented with guarded imports, raises `CameraUnavailable` off-Pi | never run on real Pi → T-HW-01 |
| 8 | USB webcam on Pi | **PARTIAL** | `PiUsbWebcamProvider` implemented (cv2/V4L2 path) | never run on real Pi → T-HW-01 |
| 9 | Dev webcam / video / mock | **COMPLETE** | Providers + tests pass; architecture records prior live verification against the physical webcam | not re-probed today (tests cover logic) |

## 10–13. Dataset engine

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 10 | Dataset Studio (UI) | **COMPLETE** | `DatasetStudio.tsx` (disk-counted stats, record/import/validate/splits) + datasets routes; 18 dataset tests pass | — |
| 11 | Dataset import & validation | **COMPLETE** | **Real ISL data ingested**: 128 MP4 clips in `data/raw/`, `data/manifests/isl40.json` (128 clips, 7 classes), 128/128 `probe_clip` pass, sha256 verified, `docs/isl40_coverage.md` | 3 vocab classes absent (PAIN/DOCTOR/TOILET) → T-DATA-03 |
| 12 | Labeling workflow | **COMPLETE** | record-from-camera, multipart import, register-in-root, explicit gloss→label mapping in `scripts/ingest_isl.py` + coverage doc | — |
| 13 | Splitting & leakage prevention | **COMPLETE** | participant-based `assign_splits` (seed 42) + **new `pin` support (uncommitted)** so identity-less sources stay train-only; `data/splits/isl40.json`; STOP has 0 test support (documented honestly) | — |

## 14–19. ML: recognition, fusion, training

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 14 | Sign recognition | **PARTIAL (model trained, live untested)** | Model `ae19271b2b19` in `models/sign/`, test 0.944 (3 unseen signers), loader+ONNX verified offline; API + frontend consume status | **live camera → fusion → dashboard never run** (T-ML-01); frontend never showed a real prediction; sign-only path blocked by default fusion policy (T-FUS-02) |
| 15 | Silent-lip recognition | **PARTIAL (code only, audited)** | Code exists (478 landmarks → 45,888-dim, `LipRecognizer`, `train_lip`, modality-aware routes/UI); audit found blockers D1–D4 (`docs/lip_phase.md`) | 0 clips, 0 models; FaceExtractor delegate bug, missing default extractor, sign-copied manifest metadata; see T-LIP-01..10 |
| 16 | Confidence-aware fusion | **COMPLETE (unit-tested)** | `fusion/` engine + policy + weights; loop wired; 10 tests; defaults `mode: both` + `allow_single_modality: false` | **with only sign installed, all sign-only predictions abstain** (T-FUS-02); E2E unverified |
| 17 | Training pipeline | **BLOCKED** | Route/worker/lock/cancel/reconcile all work (tests pass with injected extractors). Real run: job #1 (`isl40`, sign) stuck **RUNNING in `data/silentos.db` since 2026-10-27, never finished** — landmark extraction SIGKILLs (exit 137). Re-verified today: 4-frame probe survived once (GPU delegate), longer probes still Killed. Killer unidentified. | **T-ML-01 (primary blocker)**; stale job reconciles automatically at next app startup (`reconcile_stale_jobs`) but DB still shows RUNNING now |
| 18 | Model artifacts & versioning | **PARTIAL** | Writers exist (versioned `model.npz` + `model.onnx` + `manifest.json`, preprocessing_version, environment capture) and are e2e-tested with synthetic extractors | **zero real artifacts on disk**; nothing to version yet |
| 19 | Training Center (UI) | **COMPLETE** | `TrainingCenter.tsx` (job list, epoch stepper, log-driven loss curves, dataset picker) + training routes incl. new per-class metrics in `_flat_metrics` (uncommitted) | jobs submitted here will fail until T-ML-01 is resolved |

## 20–24. Output, calibration, health, privacy

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 20 | Recognition History | **COMPLETE** | DB-backed bounded history + `History.tsx` (paginated, clear); honest empty states | — |
| 21 | Calibration | **COMPLETE** | **Uncommitted new module** `calibration/` + `/api/v1/calibration/{profile,apply}` + 4 tests; honest not-calibrated/shortfall semantics, 25th-percentile tuning from real history | history is empty → real calibration profile not yet computable (by design) |
| 22 | Text & speech output | **COMPLETE** | `output/speech.py` espeak-ng wrapper, cooldown, honest unavailable; wired into fusion accept path; 5 tests | — |
| 23 | System health & device metrics | **COMPLETE** | psutil real metrics (null → "Unavailable", never fabricated), dependency probes incl. `offline_ok`; 5 health tests | temperature null on this host (honest) |
| 24 | Local storage & privacy | **COMPLETE** | SQLite + local `data/`/`models/` only, no cloud calls; binds 127.0.0.1 by default; external dataset git-ignored | — |

## 25–30. Deployment, tests, docs, hardware

| # | Area | Status | Evidence | Missing / next |
|---|---|---|---|---|
| 25 | Raspberry Pi deployment | **PARTIAL** | `docs/deployment_raspberry_pi.md` complete (deps, venv, assets, camera, run, offline verification) | no Pi available; guide untested end-to-end → T-HW-01 |
| 26 | systemd service | **PARTIAL** | Unit file documented in the deployment guide | never installed on a device → T-HW-01 |
| 27 | Offline operation | **PARTIAL** | Design is local-only; dependency probe test asserts `offline_ok`; espeak-ng honest fallback | not verified with network physically disconnected on target → T-HW-02 |
| 28 | Automated tests | **COMPLETE** | **104 backend tests pass today** (health 6, api 26, camera 16, dataset 18, sign 19, fusion 10, speech 5, calibration 4); frontend tsc/lint/build green today | no hardware/E2E suite (by design, separate suite planned) |
| 29 | Documentation | **PARTIAL** | architecture, camera, datasets, design_research, isl40_coverage, deployment, PHASE_TODO, implementation_status, skills_inventory, evidence/ all present; `README.md` fixed 2026-10-30 | training-run report (T-DOC-03) still impossible — no real training run has succeeded yet |
| 30 | Physical hardware integration | **BLOCKED** | Dev-machine webcam was verified historically; **no Raspberry Pi attached to this environment** | T-HW-01 (needs hardware) |

---

## AI / training reality check (audit section 5)

| Question | Finding |
|---|---|
| Real dataset clips imported? | **YES — 128 ISL clips** (7/10 vocab classes), manifests + splits on disk, validated & sha256-checked |
| Valid trained model exists? | **SIGN: YES** (`ae19271b2b19`, test acc 0.944 on 18 clips / 3 unseen signers; `docs/evidence/colab-run/`). **LIP: NO.** Local inference still SIGKILLed (T-ML-01). |
| Stale training job reconciled? | **NOT YET in DB** (still `RUNNING`); code reconciles at next backend startup |
| Landmark extraction works here? | **NO, not reliably.** Final bounded diagnostic (gdb, single run, 2026-10-30): `Program terminated with signal SIGKILL` at extraction n=7 with flat RSS — external SIGKILL confirmed; native abort/segfault/OOM all ruled out (0 kernel OOM events since Oct 27, `memory.max=max`, no core). Killer identity needs root-level tracing. Evidence: `docs/evidence/t-ml-01-2026-10-30/` |
| Google Colab prep exists? | **YES (implemented 2026-10-30, NOT yet executed)** — `training/notebooks/silentos_first_training.ipynb`: repo setup, env checks, HF data fetch + ingest, manifest/split/SHA-256 verification (all green when run locally), MediaPipe 1/2/4-frame gate that halts on failure, real `train_sign` call, Drive persistence, production `SignRecognizer` + ONNX verification |
| Alternative landmark backend evaluated? | **NO** — no code or dependency for any non-MediaPipe backend |
| Inference depends exclusively on MediaPipe? | **YES** — `sign/landmarks.py` and `lip/landmarks.py` are the only extraction paths |
| ASL substitution risk? | None found — vocabulary is the 10 ISL words; ASLNow benchmark is explicitly quarantined in PHASE_TODO 10f |

**Honest bottom line:** Phases 1–9 are code-complete with a green test suite and a
finished, frozen UI. The product has **no trained model**, and the one path to getting
one (MediaPipe landmark extraction) is broken on this machine. 104 passing tests prove
code paths, not accuracy; a green API smoke test proves nothing about a Raspberry Pi.
