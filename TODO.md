# SilentOS — Central TODO (single source of truth)

Created: 2026-10-30. **This file is the authoritative task registry.**
`docs/PHASE_TODO.md` remains the phase-history checklist; `docs/implementation_status.md`
is the 30-area audit. Do not create additional task lists.

Status values: `COMPLETE · PARTIAL · IN_PROGRESS · NOT_STARTED · BLOCKED · UNVERIFIED`
Software tasks (T-*) are separate from physical-hardware tasks (T-HW-*), which cannot
start until hardware is available.

---

## Phase 1–9 (foundation → calibration/deployment) — code-complete

| ID | Task | Status | Acceptance | Verify | Notes |
|---|---|---|---|---|---|
| T-FND-01 | Foundation: structure, configs, settings, SQLite | COMPLETE | app boots, config validation rejects bad values | `pytest backend/tests/test_health.py` | |
| T-API-01 | Full API surface + honesty rules | COMPLETE | all routes return honest unavailable/null semantics | `pytest backend/tests/test_api_phase2.py` | calibration route added (uncommitted) |
| T-CAM-01 | Camera providers + manager | COMPLETE | 5 providers, bounded buffer, Pi guards | `pytest backend/tests/test_camera.py` | Pi paths untested on hardware → T-HW-01 |
| T-DS-01 | Dataset engine (validate/import/record/split/export) | COMPLETE | participant splits, manifests | `pytest backend/tests/test_dataset.py` | `pin` split support added (uncommitted) |
| T-UI-01 | Dashboard redesign (Obsidian Instrument, 9 pages) | COMPLETE | tsc/oxlint/build green, historic Playwright at 4 widths | `cd frontend && npx tsc -b && npx oxlint src && npm run build` | **frozen — no redesigns** |
| T-ML-02 | Sign ML code (features/model/pipeline) | COMPLETE | parity train==infer, ONNX export | `pytest backend/tests/test_sign.py` | correctness on real data pending T-ML-01 |
| T-ML-03 | Lip ML code (mirrors sign) | COMPLETE | same honesty rules wired | `pytest backend/tests/test_dataset.py -k lip` (or full suite) | |
| T-ML-04 | Training job API (lock/precheck/cancel/logs/reconcile) | COMPLETE | no phantom jobs, 400/409 semantics | `pytest backend/tests/test_sign.py -k route` | |
| T-FUS-01 | Confidence fusion + live recognition loop | COMPLETE | abstain below floor, fused status endpoint | `pytest backend/tests/test_fusion.py` | |
| T-OUT-01 | Speech output (espeak-ng, honest fallback) | COMPLETE | cooldown, unavailable detection | `pytest backend/tests/test_speech.py` | |
| T-CAL-01 | Calibration API + engine (uncommitted) | COMPLETE | honest not-calibrated + shortfall | `pytest backend/tests/test_calibration.py` | |
| T-DOC-02 | Deployment guide, camera/datasets/architecture docs | COMPLETE | docs match code | read `docs/deployment_raspberry_pi.md` | |

Full verification for phases 1–9: `.venv/bin/python -m pytest backend/tests -q` → **104 passed** (2026-10-30).

---

## Phase 10 — Real data & first genuine model (ACTIVE)

### 10a/10b/10c — dataset integration

| ID | Task | Status | Depends on | Acceptance | Files | Verify | Blocker |
|---|---|---|---|---|---|---|---|
| T-DATA-01 | Download + ingest isl-isolated-40words target classes | COMPLETE | — | 128 clips registered, sha256 checked, 0 errors | `scripts/ingest_isl.py`, `data/manifests/isl40.json`, `docs/isl40_coverage.md` | `.venv/bin/python scripts/ingest_isl.py` (idempotent) | — |
| T-DATA-02 | Coverage report (per-class × source × license) | COMPLETE | T-DATA-01 | report lists 7/10 covered, licenses per source | `docs/isl40_coverage.md` | read file | — |
| T-DATA-03 | Collect PAIN, DOCTOR, TOILET (consented local ISL recording) | **DEFERRED** (user decision 2026-10-30: ship 7 words first) | recording workflow | ≥ MIN_TRAIN_CLIPS per class, participant metadata, no ASL/synth | `data/manifests/` new registration | ingest + re-split | needs human signers |
| T-DATA-04 | Real lip-reading dataset (own task, own eval) | NOT_STARTED | T-DATA-03-style collection | lip clips registered under lip manifest, evaluated separately | `data/manifests/*lip*` (to create) | `pytest` + train_lip precheck | needs mouth-visible recording |

### 10d — first real sign model

| ID | Task | Status | Depends on | Acceptance | Files | Verify | Blocker |
|---|---|---|---|---|---|---|---|
| T-ML-01 | **Resolve landmark-extraction SIGKILL (exit 137)** | **BLOCKED (diagnostic complete)** | root-cause first (`systematic-debugging`) | name the killer OR prove a viable local path (120-frame decode ×2 clips ×3 runs) | `backend/src/silentos/{sign,lip}/landmarks.py` | `docs/evidence/t-ml-01-2026-10-30/FINDINGS.md` | external SIGKILL at ~3 s confirmed; **killer identity needs root-level tracing (strace/bpftrace need sudo — unavailable)**; OOM, native abort, segfault, MediaPipe leak all ruled out |

**T-ML-01 evidence log (2026-10-30):**
- mediapipe 1.1.1, Python 3.14.8, Mesa Intel GPU; uncommitted GPU-first delegate patch applied.
- Probes 1–4 (earlier, read-only): 4-frame survived; longer runs died after ~6 and ~21–24 extractions; RSS flat; `memory.max=max`, `oom_kill 0`.
- **Final bounded diagnostic (gdb, single run, no pipeline masking): `Program terminated with signal SIGKILL, Killed.` at extraction n=7, RSS flat 389 MB — external SIGKILL confirmed, native abort/segfault ruled out.**
- **OOM fully ruled out:** kernel log shows 0 OOM/kill events since 2026-10-27; cgroup `memory.max=max`, `oom_kill 0`; no core dump (expected for SIGKILL).
- **Pattern:** all deaths land ~3.0–3.3 s after extraction-loop start (the only survivor finished at 2.9 s); extraction count at death varies → wall-clock-triggered external killer, not a per-frame leak. Upstream MediaPipe GPU-leak issues (#5652/#5626) do not match (flat RSS).
- **Unknown:** killer identity — needs root-level tracing (strace/bpftrace/auditd; sudo unavailable). Evidence: `docs/evidence/t-ml-01-2026-10-30/` (probe, gdb log, exit status, FINDINGS.md).
- Local training remains blocked; Colab CPU path proven (T-ML-09).
- 2026-10-30 addendum: GPU delegate also killed — EGL/GL init succeeds, then exit 137 before frame 1. Both delegates die.
- **Next diagnostic (no root):** run a 60 s non-MediaPipe compute loop (numpy + onnxruntime + plain cv2 decode). Survives → killer targets MediaPipe path → T-ML-10 workaround viable. Dies → host-wide watchdog, local inference impossible.
| T-ML-05 | Train first real sign model on isl40 (seed 42) | **COMPLETE (via T-ML-09)** | T-ML-09 | artifacts in `models/sign/` (`model.npz`, `model.onnx`, `manifest.json`, version `ae19271b2b19`); per-class metrics + confusion matrix in `docs/evidence/colab-run/evaluation.json` | training route → `models/sign/*` | manifest metrics | local route still blocked by T-ML-01 |
| T-ML-06 | Load artifact via production `SignRecognizer` + held-out eval | **COMPLETE (2026-10-30)** | T-ML-05 | loader accepts manifest, vocabulary = SilentOS labels, real held-out predictions recorded | `sign/pipeline.py` | Colab loader cell: 36 predictions on a test clip (true FOOD, 27 ms/frame) + `loader_verification.json` | local run blocked by T-ML-01 |
| T-ML-07 | Live recognition E2E with real video source | **PENDING HARDWARE/ENVIRONMENT** | T-ML-06 | camera → fusion → history with real model; latency/memory recorded | `application.py` loop | manual run, `/api/v1/recognition/status` | code path complete; live run impossible on dev host (T-ML-01); frontend never displayed a real prediction |
| T-ML-08 | Stale training job #1 reconciliation | **COMPLETE (2026-10-30)** | next backend startup | job 1 = FAILED "Interrupted by process restart" | `data/silentos.db` | startup log "Reconciled 1 stale training job(s)" | verified via app lifespan + sqlite select |
| T-ML-09 | Google Colab notebook (same repo training code) | **COMPLETE (2026-10-30)** | T-ML-01 investigation | run result: MediaPipe gate PASSED on CPU (4/4 extractions) | `training/notebooks/silentos_first_training.ipynb` | `docs/evidence/colab-run/` | trained `ae19271b2b19`: 126/128 clips, train acc 1.00, val acc 0.833, **test acc 0.944 (17/18), macro-F1 0.808** (0.943 over the 6 classes with test support); STOP has 0 test support; artifacts installed in `models/sign/` |
| T-ML-11 | `SignRecognizer` built without a landmark extractor (silent no-op) | **COMPLETE (2026-10-30)** | T-ML-09 loader verification | `pipeline.py` defaults to `models/assets/hand_landmarker.task`; regression test added | `backend/src/silentos/sign/pipeline.py`, `backend/tests/test_sign.py` | 105 tests pass | was found in both `application.py` and the notebook: live recognition would have abstained forever |
| T-ML-10 | Evaluate alternative landmark backend (only if Colab MediaPipe fails) | NOT_STARTED | T-ML-09 result | candidate runs 120-frame decode; **train/infer preprocessing parity preserved**; documented decision | spike branch/doc | probe script | gated — do not start before T-ML-09 evidence |

### 10f/10g — optional, postponed

| ID | Task | Status | Depends on | Note |
|---|---|---|---|---|
| T-DATA-05 | ASLNow benchmark (pipeline smoke only) | NOT_STARTED | T-ML-05 | never mix A–Z into word classifier; optional |
| T-DATA-06 | Investigate `aaahmet/silent-lip-reader-model` (~1 GB) | NOT_STARTED | — | investigate BEFORE download; Pi 4 GB RAM budget; keep local lip workflow regardless |

### 10h/10j — acceptance gate

| ID | Task | Status | Depends on |
|---|---|---|---|
| T-ACC-01 | Phase 10 acceptance checklist | BLOCKED | T-ML-07 | **re-scoped 2026-10-30: 7-word vocabulary, no Pi, no lip** |

---

## Phase 11 — Silent-lip model (audit complete, plan in review)

Full audit, defects and dataset plan: `docs/lip_phase.md`. Vocabulary stays at 7
words (no PAIN/DOCTOR/TOILET). Sign model is not retrained or modified.

| ID | Task | Status | Depends on | Acceptance |
|---|---|---|---|---|
| T-LIP-00 | Sign-phase verification snapshot | **COMPLETE (2026-10-31)** | — | hashes/loader/ONNX/tests/frontend build recorded in `docs/lip_phase.md` |
| T-FUS-02 | Sign-only path under default config (D5) | NOT_STARTED | policy decision | sign predictions accepted when no lip model exists; tests |
| T-LIP-01 | FaceExtractor delegate + env switch (D1) | NOT_STARTED | — | CPU-only mode on headless/Colab; no EGL abort |
| T-LIP-02 | LipRecognizer default extractor (D2) | NOT_STARTED | — | no silent no-op; regression test |
| T-LIP-03 | Correct lip manifest metadata + parity tests (D3, D6) | NOT_STARTED | — | `input_shape [1,45888]`, 478 landmarks, `lip_v1`, ONNX parity test |
| T-LIP-04 | Approve collection protocol | **IN_REVIEW** | user sign-off | protocol in `docs/lip_phase.md` §2 approved |
| T-LIP-05 | Record lip dataset (7 words) | NOT_STARTED | T-LIP-04 | quotas met; real consented clips only |
| T-LIP-06 | QC + participant-independent splits | NOT_STARTED | T-LIP-05 | QC report; zero participant overlap |
| T-LIP-07 | Colab lip training | NOT_STARTED | T-LIP-01..03, T-LIP-06 | gate passes; `models/lip/` artifacts |
| T-LIP-08 | Independent lip evaluation report | NOT_STARTED | T-LIP-07 | per-class metrics + confusion, no fusion |
| T-LIP-09 | Fusion enablement | NOT_STARTED | T-LIP-08 | §3 criteria met; sign-only still works |
| T-LIP-10 | Live lip E2E | BLOCKED | T-ML-01 / hardware | real camera + real predictions |

---

## Documentation

| ID | Task | Status | Acceptance | Verify |
|---|---|---|---|---|
| T-DOC-01 | Fix `README.md` (currently `# cornerstone`) | **COMPLETE** | README describes SilentOS, quickstart, links to docs/ | read `README.md` — rewritten 2026-10-30 with honest status table (no trained model claimed) |
| T-DOC-03 | Training-run report (after first real run) | **COMPLETE (2026-10-30)** | honest accuracy/latency/limits, baseline-model caveat, synthetic-vs-real separated | `docs/evidence/colab-run/REPORT.md` | metrics copied verbatim from the trainer/manifest |
| T-FIX-01 | `configs/default.yaml` YES/NO parsed as YAML booleans → Settings validation crash | **COMPLETE** | quoted `"YES"`/`"NO"`; regression test added; 104 tests green | `pytest backend/tests/test_health.py -k default_config` |

---

## Physical hardware (separate — cannot start without a Pi)

| ID | Task | Status | Depends on | Acceptance |
|---|---|---|---|---|
| T-HW-01 | Deploy to Raspberry Pi 4 (guide + systemd + camera) | BLOCKED | **no hardware available (user 2026-10-30)** | service runs, camera provider connects, dashboard served |
| T-HW-02 | Offline verification (network physically disconnected) | BLOCKED | T-HW-01 | all dependency probes `available: true`, no egress |
| T-HW-03 | Pi inference performance (latency/memory with real model) | BLOCKED | T-ML-06 + T-HW-01 | recorded real numbers on Pi 4 |

---

## Dependency chain (critical path)

```
T-ML-01 (MediaPipe SIGKILL root cause)
   ├─→ local path: fix → T-ML-05 → T-ML-06 → T-ML-07 → T-ACC-01
   └─→ Colab path: T-ML-09 (1/2/4-frame clean-runtime test)
          ├─ MediaPipe OK in Colab → train there with repo code → T-ML-05
          └─ MediaPipe fails → T-ML-10 (alternative backend, parity preserved)
T-DATA-03 (PAIN/DOCTOR/TOILET collection) ──→ full 10-class model (parallel track)
T-LIP-04..09 (lip phase) ──→ lip model, independent eval, then fusion   [plan: docs/lip_phase.md]
T-HW-* — all blocked on hardware, independent of software except T-HW-03
```

**Start here:** T-ML-01 (root-cause investigation, no code changes until cause is found),
with T-ML-09 (Colab) as the sanctioned parallel track per the current training strategy.
