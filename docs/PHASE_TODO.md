# SilentOS Phase Todo

> **Superseded as the task registry by `/TODO.md` (created 2026-10-30).** This file
> remains the phase-history checklist. The 30-area audit lives in
> `docs/implementation_status.md`. Checkbox states below were reconciled against the
> working tree on 2026-10-30.

Updated: 2026-10-30

## Phase 1 — Foundation
- [x] Project structure, configs, schemas, DB (SQLite)
- [x] FastAPI app factory, health/status/system metrics
- [x] Pydantic settings + env/config validation

## Phase 2 — API surface
- [x] Settings/Models/Recognition/Camera/Datasets/Diagnostics routes
- [x] Honesty rules (no fake metrics, unavailable semantics)
- [x] V4L2 camera discovery, model registry

## Phase 3 — Camera subsystem
- [x] Camera providers (mock, video_file, dev webcam, Pi variants)
- [x] Frame buffer + stats, docs/camera.md

## Phase 4 — Dataset engine
- [x] Validate/import/record/register/split/export
- [x] Participant-based splits, manifests, docs/datasets.md

## Frontend redesign (directed)
- [x] Research (8 sites + Linear/Vercel/Tabler) → `docs/design_research.md`
- [x] "Obsidian Instrument" tokens/fonts, shadcn base-nova
- [x] AppShell + all 9 pages, shared components, recharts
- [x] Browser verification at 1920/1280/1024/390, lint/tsc/build green

## Phase 5 — Sign recognition ML + training worker
- [x] `sign/` (landmarks/features/model/train/pipeline) with MediaPipe hands
- [x] Training API + daemon worker, logs (`{ts,line}`), cancellation, lock, reconcile
- [x] Strict validation (400), precheck before job row (409), ONNX export fixed
- [x] Tests + live smoke (`test_sign.py`, updated `test_api_phase2.py`)

## Phase 6 — Silent-lip recognition
- [x] `lip/` mirroring `sign/` (MediaPipe FaceLandmarker, 478 landmarks, features/model/train/pipeline)
- [x] Wire lip into training API (remove 501) with same honesty rules
- [x] Tests updated/green

## Phase 7 — Confidence-aware fusion
- [x] `fusion/` (FusionEngine + fuse_predictions, weights, policy)
- [x] Live recognition loop in Application (camera frames → sign/lip pipelines → fusion → history)
- [x] `/api/v1/recognition/status` surfaces fused `last_decision` + real `latency_ms`
- [x] Start/stop lifecycle wired (idempotent, honest 503 when no models)
- [x] `test_fusion.py` (10 tests)

## Phase 8 — Text/speech output
- [x] `output/speech.py` (`SpeechEngine`, `speak_decision`) — espeak-ng wrapper, honest unavailable detection, cooldown, thread-safe
- [x] Wired into recognition loop: speaks accepted fused labels when `speech_enabled`
- [x] Honest `last_message` when speech enabled but espeak-ng missing
- [x] `test_speech.py` (5 tests)

## Phase 9 — Calibration API + deployment
- [x] `calibration/` (`CalibrationEngine`, `compute_profile`) — honest not-calibrated + shortfall; 25th-percentile threshold tuning from real history
- [x] `/api/v1/calibration/profile` (GET) + `/api/v1/calibration/apply` (POST)
- [x] `test_calibration.py` (4 tests)
- [x] `docs/deployment_raspberry_pi.md` — full Pi 4 deployment guide

### Phases 1–9 code-complete: 104 backend tests passing (verified 2026-10-30).
### ⚠ HONEST STATE: `models/sign/` and `models/lip/` are EMPTY — no model has been
### trained on real data yet. The 102 tests validate code paths, not accuracy.

---

## Phase 10 — Real dataset integration + first genuinely trained model (ACTIVE)

User directive: do not claim SilentOS has a trained/accurate model until real data
is processed, training completes, and evaluation runs.

### 10a. Audit existing implementation
- [x] Feature dims: sign 2016 (32×21×3), lip 45888 (32×478×3); wrist-relative +
  per-frame scale normalize + linear 32-frame resample; MIN_FRAMES=8
- [x] Training format: dataset manifest (`data/manifests/{id}.json`) + `ClipRecord`
  rows; participant-based splits required; `MIN_TRAIN_CLIPS=4`, `MIN_CLASSES=2`
- [x] Artifact format: `model.npz` (W,b,μ,σ,classes) + `model.onnx` (Sub→Div→MatMul→
  Add→Softmax) + `manifest.json`
- [x] Inference input: same `sequence_to_features` path (train/infer parity confirmed)
- [x] Class mapping: model.classes are the manifest labels (must map to SilentOS
  vocabulary)
- [x] Worker capacity: daemon worker decodes clips synchronously — fine for a ~100-clip
  dataset; full-batch GD trains in seconds on this data size

### 10b. Investigate + integrate real ISL data (PRIMARY: vidit031/isl-isolated-40words)
- [x] Dataset card verified: 642 MP4 clips, 40 glosses, 480p, ~30 FPS
- [x] License verified: `other` — multi-source aggregate (ISL500 405, INCLUDE 143
  CC-BY-4.0, CISLR 81 AFL-3.0, ISLRTC 13 MIT+data.gov); research/education use
- [x] metadata.csv fetched + analyzed (642 rows, 40 classes, quality 0.85–1.00,
  all `unique`, 617 `accepted` / 25 `Needs Manual Review`)
- [x] Target mapping verified: HELP 16, WATER 18, FOOD 17, YES 17, NO 17, STOP 4,
  THANK YOU 39 → **7/10 present**; **PAIN, DOCTOR, TOILET MISSING**
- [x] Download target-class clips via HF tooling (outside Git) — 128 clips, `data/external/`
- [x] Coverage report written (per-class × source × license) — `docs/isl40_coverage.md`
- [x] Reproducible dataset manifest (revision SHA `255ce7fd…`) — `data/manifests/isl40.json`

### 10c. Real-data ingestion path
- [x] Dedicated adapter: source video + original label → mapped SilentOS label +
  ClipRecord manifest (preserves source, license, duration, frames, status/errors) —
  `scripts/ingest_isl.py`
- [x] Actual validation: 128/128 `probe_clip` pass, 0 errors, sha256 spot-checked 8/8,
  disk↔metadata 128/128 (recorded in `docs/isl40_coverage.md`)
- [x] Participant-aware splits: ISL500 real signers held out; identity-less sources
  pinned train-only (`pin` in `assign_splits`) — documented limitation: STOP has 0
  test support

### 10d. Train first real sign model
- [ ] Train LogisticBaseline on real mapped data (deterministic seed)
- [ ] Save: config, dataset manifest + splits, model.npz, model.onnx, manifest.json,
  logs, evaluation, confusion matrix, per-class precision/recall/F1, accuracy,
  macro-F1, preprocessing + vocabulary mappings
- [ ] No threshold tuning on test set; honest report if too small for held-out eval

### 10e. Coverage gaps (PAIN, DOCTOR, TOILET)
- [ ] Coverage report lists missing classes
- [ ] Collect via existing local recording workflow (consent, verified ISL labels,
  session/participant metadata) — NO ASL substitutes, NO synthesized/duplicated clips

### 10f. ASLNow benchmark (separate, optional)
- [ ] Inspect `sid220/asl-now-fingerspelling` JSON schema + labels first
- [ ] Use ONLY to test landmark ingestion/classification pipeline; never mix A–Z
  labels into the SilentOS word classifier

### 10g. Lip-reading options (separate)
- [ ] Investigate `aaahmet/silent-lip-reader-model` (architecture, size ~1 GB,
  deps, decoder, license, Pi 4 GB RAM budget) BEFORE download
- [ ] Document integration work required if incompatible; keep local lip recording/
  evaluation workflow

### 10h. Verify complete inference path
- [ ] Load artifact via production `SignRecognizer` loader
- [ ] Verify manifest + vocabulary; inference on held-out real clips
- [ ] Preprocessing parity (train == infer); labels map to SilentOS classes
- [ ] Live recognition loop with real video source; confidence/abstention tested
- [ ] No unsupported-class predictions; record actual latency + memory on this machine

### 10i. Colab (only if laptop environment blocked)
- [ ] Reproducible notebook using the SAME repo training code (no notebook-only
  pipeline); verifiable artifact download
  — **notebook implemented 2026-10-30** (`training/notebooks/silentos_first_training.ipynb`,
  local-safe cells executed green); checkbox stays open until a real Colab run
  completes the gate → train → artifact → loader chain

### 10j. Acceptance criteria
- [ ] Real dataset lawfully accessed
- [ ] Validation + class coverage recorded
- [ ] Model trained on real labeled data (or concrete blocker documented)
- [ ] Saved artifact loaded by actual model loader
- [ ] Held-out evaluation results generated
- [ ] Vocabulary mapping correct
- [ ] Live inference path tested as far as data/hardware permit
- [ ] Synthetic smoke tests clearly distinguished from real-data experiments
- [ ] Documentation + TODO statuses reflect actual results
