# Colab gate run 1 — GPU delegate aborts on missing EGL (2026-10-30)

## Environment
- Google Colab, runtime `gpu-t4-s-use1c0-1s8xjrvfrt23d`, Python 3.12, mediapipe 0.10.x
- Repo: Option C (`/content/cornerstone`, from `MyDrive/silentos.zip`)
- Sections 3–5 passed: revision check, manifest/split verification, sha256 128/128

## Symptom
Section 6 (MediaPipe gate) aborted the kernel during `HandExtractor` construction,
before any frame extraction. Colab then restarted the kernel; the cell re-ran in a
fresh kernel and raised `ModuleNotFoundError: No module named 'silentos'`
(collateral — section 3's `sys.path` setup was lost on restart).

```
W0000 gl_context_egl.cc:214] Failed to get default EGL display, trying multi-gpu EGL display selection.
E0000 gl_context_egl.cc:112] INTERNAL: RET_CHECK failure (third_party/mediapipe/gpu/gl_context_egl.cc:112) egl_initialized Unable to initialize EGL
Stack trace:
  mediapipe::GlContext::CreateContext()
  mediapipe::GpuResources::Create()
  mediapipe::GraphService<>::CreateDefaultObject()
  mediapipe::CalculatorGraph::PrepareServices()
  mediapipe::tasks::vision::hand_landmarker::HandLandmarker::Create()
  hand_landmarker::CppHandLandmarkerCreate()
AsyncIOLoopKernelRestarter: restarting kernel (1/5)
```

## Cause
`backend/src/silentos/sign/landmarks.py` forced `BaseOptions.Delegate.GPU` first
(the T-ML-01 laptop workaround, where the CPU delegate is SIGKILLed). MediaPipe's
GPU delegate requires EGL; the Colab container has no EGL display, so
`create_from_options()` hits a C++ `LOG(FATAL)` and aborts the process.
`LOG(FATAL)` cannot be caught by Python, so the `try/except` fallback to CPU never runs.

This is a **different failure from T-ML-01**: the laptop kill is an external SIGKILL
on the CPU delegate (`status: running`, process vanishes, no EGL message, no abort).

## Fix
`delegate_order()` in `landmarks.py`: default `("gpu", "cpu")` (unchanged laptop
behaviour), `SILENTOS_MEDIAPIPE_DELEGATE=cpu` → `("cpu",)`. The notebook gate cell
sets that env var before importing `silentos` and records the choice in
`mediapipe_test_result.json` under `"delegate"`.

## Next
Re-run Colab with the updated zip. Gate must print
`MEDIAPIPE GATE: PASSED — 4 total extractions over checkpoints 1, 2, 4` on CPU.
