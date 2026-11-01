# SilentOS — Windows Setup Guide (run on another laptop)

Goal: backend + dashboard + trained sign model + webcam on a Windows 10/11
machine. Everything runs locally on `127.0.0.1:8000` — no internet needed
after installs.

**Transfer package:** `silentos-transfer.zip` (copy via USB / drive / etc.).
It contains: `backend/`, `configs/`, `data/manifests/`, `frontend/` (source +
prebuilt `dist/`), `models/` (trained sign model + MediaPipe assets),
`scripts/`, `training/`, `docs/`, `pyproject.toml`, `README.md`.

It does **not** contain: `.venv`, `node_modules`, `.git`, local database —
all recreated below.

---

## 1. Install prerequisites (one time)

1. **Python 3.12** — download from https://www.python.org/downloads/
    - During install: **check "Add python.exe to PATH"**
    - Verify in PowerShell: `python --version` → must print 3.12.x
    - (3.12 specifically — the MediaPipe camera library ships Windows wheels
      for 3.12; newer versions may not)
2. **Optional — Node.js LTS** (only if you want to edit the UI code; not
   needed to run the app): https://nodejs.org

## 2. Extract

Extract the zip to **`C:\silentos`** (no spaces in the path — important).

```
C:\silentos\
  backend\   configs\   models\   frontend\   scripts\   ...
```

## 3. Set up the backend (PowerShell)

Open PowerShell in `C:\silentos` (folder → "Open in Terminal"):

```powershell
cd C:\silentos
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -e ".[inference,vision]"
```

First run downloads MediaPipe + ONNX wheels (~200 MB, one time).

## 4. Run it

```powershell
cd C:\silentos
$env:SILENTOS_CONFIG="./configs/development.yaml"
.\.venv\Scripts\python -m uvicorn silentos.main:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in Chrome/Edge — the dashboard loads from the
same server (the built frontend in `frontend\dist`).

Keep that PowerShell window open while using the app. To stop: `Ctrl+C`.

## 5. First-run configuration

1. **Recognition mode → sign** (the lip model is intentionally not trained;
   in "both" mode every prediction would abstain). Either:
    - Dashboard → _Device Settings_ → Recognition mode → **sign**, or

    ```powershell
    Invoke-RestMethod -Method Put -Uri http://127.0.0.1:8000/api/v1/settings `
      -ContentType "application/json" -Body '{"recognition_mode":"sign"}'
    ```

2. Camera panel → **Live Vision** → allow the browser's camera permission
   if asked. You should see yourself (640×480).

## 6. Test the trained model

Click **Start recognition** (Runtime panel). Expected:

- Sign model loads (`ae19271b2b19`, 7 words) — status turns LOADED
- Camera state CONNECTED, inference latency appears
- Hold **one sign at a time**, steady ~1 s, palm toward the camera:
  **HELP, WATER, FOOD, YES, NO, STOP, THANK YOU**
- Predictions appear in _Latest Recognition_ + _Recognition History_

This is the full live loop that the original laptop blocks (T-ML-01: its
MediaPipe gets SIGKILLed by that specific Arch/Mesa machine). On a normal
Windows laptop extraction is expected to run — that's the point of testing
here.

### If Start recognition shows a refusal toast

Same honest refusal as the original machine (extraction died here too). One-shot
alternative — stops after 10 frames, prints a single prediction:

```powershell
cd C:\silentos
.\.venv\Scripts\python scripts\test_sign_live.py
```

---

## Troubleshooting

| Symptom                                | Fix                                                                                    |
| -------------------------------------- | -------------------------------------------------------------------------------------- |
| `address already in use` on port 8000  | Another copy is running — close it or use `--port 8001`                                |
| Camera preview black / busy            | Only one program can hold the webcam — close other camera apps                         |
| `py -3.12` not found                   | Python not on PATH or not 3.12 — re-run installer with "Add to PATH", or use full path |
| MediaPipe pip install fails            | Wrong Python version — must be 3.12 (`.\.venv\Scripts\python --version`)               |
| Predictions never appear after Start   | Mode is still `both` — set it to `sign` (step 5)                                       |
| `Lip model: NOT_TRAINED`               | Normal — lip phase is a later stage                                                    |
| `Speech: disabled`                     | Normal — speech engine (espeak) not installed; not needed for recognition              |
| Dashboard loads but camera panel empty | Click Live Vision; check browser camera permission for `127.0.0.1`                     |

## Optional: UI development on this machine

Only needed to edit the dashboard code:

```powershell
cd C:\silentos\frontend
npm install
npm run dev        # → http://localhost:5173 (hot reload, proxies API to :8000)
npm run build      # refresh the production build served by the backend
```

## Notes

- All data stays local (offline-first). Nothing is uploaded anywhere.
- The trained model files live in `models\sign\` (`model.npz`, `manifest.json`);
  the hand-landmark asset is `models\assets\hand_landmarker.task`.
- Re-running setup after copying to another PC: repeat sections 3–4 only.
