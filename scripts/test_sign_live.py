#!/usr/bin/env python
"""One-shot live test of the trained sign model on this machine's webcam.

T-ML-01-aware: stops after 10 frames (the laptop's extraction SIGKILL window
starts around 15+ detect calls), enough for the 8-detection MIN_FRAMES gate.
Run while holding one of the 7 trained signs: HELP, WATER, FOOD, YES, NO,
STOP, THANK YOU.

  .venv/bin/python scripts/test_sign_live.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import cv2  # noqa: E402

from silentos.sign.pipeline import SignRecognizer  # noqa: E402

MAX_FRAMES = 10  # stay under the T-ML-01 kill window (~15+ extracts)


def release_backend_camera() -> None:
    """The dashboard preview holds /dev/video0 exclusively; let it go."""
    import urllib.request

    try:
        urllib.request.urlopen(
            "http://127.0.0.1:8000/api/v1/camera/stop", timeout=3
        ).read()
    except OSError:
        pass  # backend down — camera is free anyway


def main() -> int:
    rec = SignRecognizer(ROOT / "models" / "sign" / "model.npz")
    print(f"model: loaded={rec.available} labels={rec.labels}", flush=True)
    if not rec.available:
        print("model.npz not found — restore models/sign/ artifacts", flush=True)
        return 1

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        release_backend_camera()
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("camera /dev/video0 could not be opened", flush=True)
        return 1

    try:
        for i in range(1, MAX_FRAMES + 1):
            ok, frame = cap.read()
            if not ok:
                print("frame read failed", flush=True)
                return 1
            label, conf, landmarks = rec.predict_frame(frame)
            hand = "hand" if landmarks is not None else "no-hand"
            conf_s = f"{conf:.3f}" if conf is not None else "-"
            print(f"  frame {i}/{MAX_FRAMES}: {hand} -> {label} ({conf_s})", flush=True)
            if label is not None:
                print(f"PREDICTION: {label}   confidence={conf:.3f}", flush=True)
                return 0
        print(
            "no decision in 10 frames — hold the sign steady, "
            "palm facing the camera, and rerun",
            flush=True,
        )
        return 2
    finally:
        cap.release()
        rec.close()


if __name__ == "__main__":
    sys.exit(main())
