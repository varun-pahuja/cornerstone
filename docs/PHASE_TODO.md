# SilentOS Phase Todo

Updated: 2026-10-27

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
- [x] 83 backend tests passing

## Phase 6 — Silent-lip recognition
- [x] `lip/` mirroring `sign/` (MediaPipe FaceLandmarker, 478 landmarks, features/model/train/pipeline)
- [x] Wire lip into training API (remove 501) with same honesty rules
- [x] Tests updated/green

## Phase 7 — Confidence-aware fusion
- [x] `fusion/` (FusionEngine + fuse_predictions, weights, policy)
- [x] Live recognition loop in Application (camera frames → sign/lip pipelines → fusion → history)
- [x] `/api/v1/recognition/status` surfaces fused `last_decision` + real `latency_ms`
- [x] Start/stop lifecycle wired (idempotent, honest 503 when no models)
- [x] `test_fusion.py` (10 tests) — total 93 backend tests passing

## Phase 8 — Text/speech output
- [x] `output/speech.py` (`SpeechEngine`, `speak_decision`) — espeak-ng wrapper, honest unavailable detection, cooldown, thread-safe
- [x] Wired into recognition loop: speaks accepted fused labels when `speech_enabled`
- [x] Honest `last_message` when speech enabled but espeak-ng missing
- [x] `test_speech.py` (5 tests) — total 98 backend tests passing
- [x] Live smoke: enable/disable speech, diagnostics probe shows `espeak-ng False`

## Phase 9 — Calibration API + deployment
- [ ] Calibration endpoints + UI wiring
- [ ] Raspberry Pi deployment notes/docs
- [ ] E2E smoke + final verification
