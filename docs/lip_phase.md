# Lip recognition phase — implementation audit & dataset plan

Date: 2026-10-31 · Status: **audit complete, no code changed** · Scope: 7-word
vocabulary (HELP, WATER, FOOD, YES, NO, STOP, THANK YOU). PAIN / DOCTOR / TOILET
stay out. Sign model is not retrained, replaced, or modified.

---

## 0. Sign-phase verification snapshot (before lip work)

Verified on 2026-10-31, after commit `95b06bf`:

| Check | Result |
|---|---|
| Artifacts present | `models/sign/{model.npz,model.onnx,manifest.json}` |
| Version | `ae19271b2b19`, 7 labels |
| `model.npz` sha256 | `ae19271b2b1978e2b934085e40b37015a07dc512d6aa1db5df67788529699436` |
| `model.onnx` sha256 | `95c2dea6f5e4317a46a1db814e905f418244755b657832818437b4dfec14df53` |
| `manifest.json` sha256 | `ac3e092dd6e3aad2db0fd2256624b91522b497ba74fe35a796de27d2008a796a` |
| Loader | `SignRecognizer` loads model + manifest; default extractor = `models/assets/hand_landmarker.task` |
| ONNX | loads via onnxruntime, shape `(1, 7)`, probs sum `1.0` |
| Backend API | `/api/v1/recognition/status` exposes `sign_model_status`; routes unchanged |
| Frontend | `npm run build` green; Overview / SystemHealth / LiveVision / AiLab consume model status |
| Tests | 105 passed |
| Preprocessing | `sign_v1`, 21 landmarks × 3 × 32 frames = 2016 dims |

**Code-level integration vs verified functionality**

- Code-level: complete for sign — model load, ONNX export, API status, frontend
  consumption, fusion wiring.
- Verified end-to-end: **only offline/Colab** (loader + ONNX + 36 predictions on a
  held-out clip). **Live camera → fusion → dashboard is untested** and blocked on
  this host by T-ML-01 (MediaPipe SIGKILL). Frontend has never displayed a real
  prediction.

**Artifact restore on a fresh clone** (`models/` is gitignored — the model is NOT
in Git):

```bash
mkdir -p models/sign models/assets
# from Google Drive: SilentOS_artifacts/ae19271b2b19/
cp model.npz model.onnx manifest.json models/sign/
# landmark assets (task files) are also not in Git; restore from a backup
cp hand_landmarker.task face_landmarker.task models/assets/
sha256sum models/sign/*   # must match the hashes above
```

Any mismatch means a different/partial artifact set — do not claim it is
`ae19271b2b19`.

---

## 1. Component audit

| Component | Implemented | Works | Gaps |
|---|---|---|---|
| `lip/landmarks.py` (`FaceExtractor`) | yes, 478 landmark points, VIDEO mode | no (untested) | **D1** |
| `lip/features.py` | yes: per-frame translate+scale norm, resample to 32, flat 45,888 dims | unit-tested | **D4** |
| `lip/model.py` (`LogisticBaseline`, shared) | yes: softmax regression, npz + ONNX | tested via sign | none |
| `lip/pipeline.py` (`LipRecognizer`) | yes: buffer 96, MIN_FRAMES 8, confidence floor 0.45 | no (untested) | **D2** |
| `lip/train.py` (`train_lip`, `validate_request`) | yes: stride-2 decode, ≤120 frames, eval, export | no (never run) | **D3** |
| Training route (modality branch) | yes: lock/logs/cancel/reconcile, `modality=lip` | tested with fakes | none |
| Dataset (modality=`lip`, participant splits, `pin`) | yes | tested | no face-visibility QC |
| Fusion engine + policy | yes: thresholds, abstain, agree/disagree | tested with fakes | **D5**, weights hardcoded 0.6/0.4 |
| Frontend (Dataset Studio recorder, Training Center, AiLab, LiveVision) | yes: modality selector `sign`/`lip`, lip model status | build green | never run with a lip model |
| Lip data / lip model / lip evaluation | **absent** | — | the actual work |

### Defects to fix before any lip training (D1–D3 are blockers)

- **D1 — `FaceExtractor` forces the GPU delegate** and has no env switch. This is
  the exact bug that aborted Colab for sign (`gl_context_egl.cc` → `LOG(FATAL)`).
  On Colab, lip extraction would die at `create_from_options` with no catchable
  exception. Must reuse the sign fix (`delegate_order()` / `SILENTOS_MEDIAPIPE_DELEGATE=cpu`).
- **D2 — `LipRecognizer` has no default extractor.** `application.py` builds
  `LipRecognizer(model_path)`; `predict_frame` then returns `(None, None, None)`
  forever (same class of bug as T-ML-11). Must default to
  `models/assets/face_landmarker.task`, or the lip recognizer is a silent no-op.
- **D3 — `train_lip` writes sign's metadata**: `input_shape [1, 2016]`,
  `feature.landmarks 21`, `dim 2016`, `preprocessing_version "sign_v1"`, and log
  lines saying "Sign model". The real lip shape is `[1, 45888]`, 478 landmarks.
  Wrong manifests would mislead every downstream consumer.
- **D4 — 45,888 features vs a small dataset.** 478 points × 3 × 32 is ~23× the
  sign feature size; with a few hundred clips the baseline will overfit and the
  npz/ONNX grow accordingly (W is 45,888×7). Decision needed before recording:
  (a) keep all 478 points (simple, parity with current code), or (b) restrict to
  the mouth/chin region (~40 points → ~3,840 dims) with a documented
  `preprocessing_version` bump (`lip_v1`). Must not silently change after data
  exists; either way, train/infer parity stays mandatory.
- **D5 — default fusion policy defeats sign-only.** `recognition.mode: both` with
  `fusion.allow_single_modality: false` means a sign-only prediction is
  *abstained* (`single_modality_disabled`), so the shipped default config produces
  no output even with the sign model installed. With no lip model, lip is always
  `None`, so this is permanent. Options: `mode: sign`, `allow_single_modality:
  true`, or code that enables single-modality when only one model is loaded.
  Decide before any live test; the sign-only path must stay functional.
- **D6 — no lip-specific tests** for manifest shape, parity, or default extractor.

### Genuinely missing (no code exists)

1. Lip clips (0 recorded).
2. Lip model artifacts (`models/lip/` empty).
3. Face-detection QC pass over recorded clips.
4. Independent lip evaluation report.
5. Lip section in the Colab notebook.
6. Any lip documentation for users.

---

## 2. Dataset collection plan (approve before recording)

### 2.1 Non-negotiables

- Real, consented, mouth-visible recordings only. **No synthetic samples, no
  LipNet-style pre-made datasets masquerading as our data, no augmentation
  counted as new participants.**
- Participant-independent splits. No video from a participant appears in two
  splits.
- 7 labels only: HELP, WATER, FOOD, YES, NO, STOP, THANK YOU. Unlisted labels are
  rejected by dataset validation (vocabulary from `configs/default.yaml`).
- Data stays local (`data/`, gitignored).

### 2.2 Participants

| Split | Participants | Clips per class per participant | Purpose |
|---|---|---|---|
| train | 3–5 | 8–10 | learn |
| val | 1–2 | 4–6 | model/threshold selection |
| test | 1–2 | 4–6 | final untouched report |

Minimum viable dataset: **4 participants → 2 train / 1 val / 1 test**, 8 train
clips per class. Recommended: 6 participants. With 7 classes and 8 clips that is
56 train clips, plus 28 val, 28 test.

### 2.3 Recording protocol (per clip)

- Silent mouthing, **mouth fully visible**; no hand covering the mouth, no mask.
- Front-facing, head reasonably still; shoulders and chin in frame.
- Neutral, even lighting; avoid strong backlight. Same room per participant session.
- Clip length 1.5–3 s; one word per clip, two takes per word per "take round".
- Camera height near eye level; 640×480 minimum, 15–30 fps.
- Record each word at least twice per participant per session (repetition helps
  the model see natural variation). Sessions may be repeated on another day.
- Do not coach exaggerated mouth shapes; natural articulation.

### 2.4 How to record (existing UI, no new code)

1. Start backend + frontend (see README).
2. Dataset Studio → choose camera → **modality = `lip`** → label = one of the 7 →
   participant id (e.g. `lip-p01`) → record.
3. Repeat until the per-participant quota is met; keep the same participant id
   across sessions (`lip-p01`, and record the session in the label notes).
4. Clips land in `data/raw/` and are registered in `data/manifests/<dataset>.json`.
5. Export/inspect the manifest counts by modality and label.

### 2.5 QC gate (before splits)

Run these checks (script/notebook cell) and store the report next to the manifest:

1. **Face present** in ≥ 8 of every 2nd frame (same stride the trainer uses),
   otherwise the clip is excluded with a reason.
2. **Motion**: landmark variance above a small threshold — rejects a static
   mouth or a clip where the word is not articulated.
3. **Duration/resolution/fps** recorded in metadata; reject clips < 1.2 s.
4. **Duplicate detection** by content hash (same file recorded twice).
5. Report per participant × class counts; flag any class with zero test support
   (this is what happened to `STOP` in sign — do not repeat it silently).

Only clips passing QC are registered for training. Counts are reported verbatim;
a class that fails QC is reported as missing, never padded.

### 2.6 Splits

- Participant-based, pinned: `manifest.splits.participants` maps every participant
  to exactly one of `train`/`val`/`test`.
- Assertion: intersection of participant sets across splits is empty.
- Assertion: every class appears in train; val/test coverage reported honestly.
- No re-splitting after seeing test results.

---

## 3. Training & evaluation plan

1. Fix D1 → D3 (+ D6 tests) first; bump `preprocessing_version` to `lip_v1`.
2. Decide D4 (all 478 points vs mouth region) **before** recording, so features
   can't change after data exists.
3. Extend the Colab notebook with a lip section that reuses `train_lip`, the same
   pinned dataset revision discipline, and the CPU delegate.
4. Train in Colab (local extraction remains blocked by T-ML-01).
5. Evaluate **independently of fusion**: per-class precision/recall/F1, confusion
   matrix, macro-F1 over classes with support, val and test reported separately,
   abstain rate at the production confidence floor.
6. No tuning on test; no threshold chosen from test data.
7. Only after the report exists: enable lip in fusion (D5 decision, weights
   currently hardcoded `sign=0.6, lip=0.4` → make configurable before mixing).

### Fusion enablement criteria (proposed, to be agreed before training)

- lip test macro-F1 ≥ 0.60 over classes with test support (mouthing is harder than
  signing; this is a floor, not a success claim), and
- val/test do not suggest the model collapsed onto one class, and
- sign-only path still produces predictions (D5 resolved), and
- abstain behaviour verified at the configured floor.

---

## 4. Tasks

| ID | Task | Status | Depends | Acceptance |
|---|---|---|---|---|
| T-LIP-00 | Sign-phase verification snapshot | **COMPLETE (2026-10-31)** | — | hashes/loader/ONNX/tests/frontend build recorded |
| T-FUS-02 | Sign-only path under default config (D5) | NOT_STARTED | decision | sign predictions accepted with no lip model; tests |
| T-LIP-01 | FaceExtractor delegate + env switch (D1) | NOT_STARTED | — | CPU-only mode; no EGL abort; unit test |
| T-LIP-02 | LipRecognizer default extractor (D2) | NOT_STARTED | — | never a silent no-op; regression test |
| T-LIP-03 | Correct lip manifest metadata + parity tests (D3, D6) | NOT_STARTED | — | `input_shape [1,45888]`, 478 landmarks, `lip_v1`, ONNX parity test |
| T-LIP-04 | Approve collection protocol (this doc) | **IN_REVIEW** | you | sign-off before recording |
| T-LIP-05 | Record lip dataset (7 words) | NOT_STARTED | T-LIP-04 | quotas per §2.2 met; real clips only |
| T-LIP-06 | QC + participant splits | NOT_STARTED | T-LIP-05 | QC report; zero participant overlap |
| T-LIP-07 | Colab lip training | NOT_STARTED | T-LIP-01..03, T-LIP-06 | gate passes; artifacts in `models/lip/` |
| T-LIP-08 | Independent lip evaluation report | NOT_STARTED | T-LIP-07 | per-class metrics + confusion; no fusion |
| T-LIP-09 | Fusion enablement | NOT_STARTED | T-LIP-08 | criteria §3 met; sign-only still works |
| T-LIP-10 | Live lip E2E | BLOCKED | T-ML-01 / hardware | real camera + real predictions |

---

## 5. What stays untouched

- `models/sign/*` — no retraining, no replacement, no threshold changes.
- `sign/` code paths and `preprocessing_version = sign_v1`.
- API contracts and frontend pages (only additive changes at most, later).
- Fusion behaviour for sign until T-FUS-02 is decided.

**Live recognition is not claimed to work anywhere.** Sign is verified offline
(loader + ONNX + one held-out clip) and pending hardware/environment testing for
live camera and frontend real-prediction display. Lip has no model at all.
