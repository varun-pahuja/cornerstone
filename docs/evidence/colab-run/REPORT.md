# First real training run — sign model `ae19271b2b19`

Date: 2026-10-30 · Task: T-ML-09 / T-ML-05 · Status: **model trained, evaluated,
installed, loader-verified in Colab** · Local inference still blocked (T-ML-01).

## What was trained

| Item | Value |
|---|---|
| Model type | `LogisticBaseline` (logistic regression on 2016-dim landmark features) — not a deep network |
| Version | `ae19271b2b19` (`trained_at` 2026-10-30T18:05:15Z) |
| Dataset | `vidit031/isl-isolated-40words`, revision `255ce7fd10da5d05bc30d59668ba256e5f02531c` |
| Clips | 126 of 128 usable (2 skipped: `water__CISLR__00010__5FSC6Og1RBQ_2.mp4`, `yes__CISLR__00034__MXmTYGHWvvE.mp4`) |
| Classes | FOOD, HELP, NO, STOP, THANK YOU, WATER, YES (7 of 10) |
| Features | 21 landmarks × 3 coords, resampled to 32 frames → 2016 dims, `sign_v1` |
| Splits | train 90 clips / 12 signers · val 18 / 3 · test 18 / 3 (participant-disjoint) |
| Hyperparameters | epochs 40, lr 0.5, l2 0.001, seed 42 |
| Training time | 190 s on Colab T4 runtime (MediaPipe on CPU) |
| Environment | Colab Python 3.12, mediapipe 1.2.0, numpy 2.1.3 (laptop venv: mediapipe 1.1.1, numpy other) |

## MediaPipe gate (precondition)

CPU delegate, cumulative 1 → 2 → 4 extractions: **PASSED** (4 total, RSS flat
~1015 MB). The GPU delegate aborts the Colab process on missing EGL, so the gate
cell pins `SILENTOS_MEDIAPIPE_DELEGATE=cpu`.

## Results (verbatim from the trainer)

| Split | Clips | Accuracy | Macro-F1 |
|---|---|---|---|
| train | 90 | 1.000 | 1.000 |
| val | 18 | 0.833 | 0.701 |
| **test (unseen signers)** | 18 | **0.944** | **0.808** |

Macro-F1 over the six classes that have test support is **0.943**; the 0.808
figure includes `STOP`, which has **0 test support** (all 4 clips are in train).

Test confusion (rows = true): one `NO` → `WATER`. Val additionally has
`THANK YOU` recall 0.33 (2 → `FOOD`).

Final training loss 0.01533 (from 2.045 at epoch 1, with a spike to 4.045 at
epoch 2). Train accuracy 1.0 means memorisation of the 90 training clips — the
test number is the one that counts.

## Loader verification (production path)

`SignRecognizer` + ONNX export on held-out test clip
`raw/User001/isl500/food__ISL500__00084__Food__session108__clip023.mp4`
(true label FOOD, participant User001):

- 36 predictions over 163 frames (first at frame 51, once 8 landmarks buffer)
- all `FOOD`, confidence ≈ 1.0
- 4.39 s → ~27 ms/frame (MediaPipe CPU)
- ONNX single forward pass: shape (1, 7), probs sum 1.0000

## Honest limitations

- 3 test clips per class: ±1 clip ≈ ±5.6 accuracy points. The 0.944 is a small-sample result.
- `STOP` cannot be validated (0 val/test clips) and is learned from 4 examples.
- Confidence saturates at 1.0 — certainty, not calibration.
- Two clips produced no usable hand sequence.
- Does not cover PAIN, DOCTOR, TOILET (no data; deferred).
- Never run against a live camera or on the Pi; local MediaPipe is SIGKILLed on the
  dev laptop (both delegates; see `docs/evidence/t-ml-01-2026-10-30/FINDINGS.md`).

## Artifacts

- `models/sign/model.npz`, `model.onnx`, `manifest.json` (laptop)
- `docs/evidence/colab-run/evaluation.json`, `environment.json`, `training_log.txt`,
  `mediapipe_test_result.json`
- `loader_verification.json` — in Drive `SilentOS_artifacts/ae19271b2b19/`

## Reproduction

1. `training/notebooks/silentos_first_training.ipynb` in Colab (T4 runtime), sections 2 → 10.
2. Option C: mount Drive, extract `silentos.zip` to `/content/cornerstone`.
3. Gate must print `MEDIAPIPE GATE: PASSED`; then training, evaluation, Drive persist,
   loader verification.
