"""Extraction health probe (guard for T-ML-01).

On some hosts MediaPipe landmark extraction is SIGKILLed with no traceback.
The kill lands inside whatever process touches it, so for the API server one
training run or one recognition start takes uvicorn itself down and the
dashboard floods the log with ECONNREFUSED. Nothing in-process can catch a
SIGKILL — the only guard is to run one real extraction workload in a child
process, cache the verdict, and refuse the work with an honest message.

Child entry point (also usable by hand):
    python -m silentos.vision_gate <raw_dir> <hand_landmarker_task>
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("silentos.vision_gate")

# 100 extracts: on the dev host the SIGKILL threshold is racy between ~15 and
# ~50 detect_for_video calls (measured 2026-10-31), and a shallow probe (10)
# false-passed and let training kill uvicorn. 100 sits well above the observed
# window while staying a couple of seconds on healthy hosts.
# ponytail: probabilistic probe — a racy host can still slip through; the hard
# ceiling is moving train_sign into a child process (T-ML-13) so a SIGKILL
# can never take the API server down with it.
PROBE_EXTRACTS = 100
PROBE_TIMEOUT_S = 90.0
# Dev runs load silentos via `--app-dir backend/src`, so the child needs
# this directory on PYTHONPATH whether or not the package is installed.
_BACKEND_SRC = Path(__file__).resolve().parents[1]


def _child(raw_dir: str, model_path: str) -> int:
    """Child body: decode one real frame, run the real extractor like training does."""
    import cv2
    import numpy as np

    from .sign.landmarks import HandExtractor

    frame = None
    for pattern in ("*.mp4", "*.avi", "*.mov"):
        for clip in sorted(Path(raw_dir).rglob(pattern))[:1]:
            cap = cv2.VideoCapture(str(clip))
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None:
                break
            frame = None
        if frame is not None:
            break
    if frame is None:
        # No clips yet: a striped frame still drives the same task path.
        frame = np.zeros((480, 640, 3), np.uint8)
        frame[:, ::4] = 255

    extractor = HandExtractor(model_path)
    for _ in range(PROBE_EXTRACTS):
        extractor.extract(frame)
    print("PROBE_OK", flush=True)
    return 0


def probe_extraction(raw_dir: Path, model_path: Path) -> tuple[bool, str]:
    """(ok, detail): run one real extraction workload in a child process."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(_BACKEND_SRC), env.get("PYTHONPATH", "")) if p
    )
    cmd = [sys.executable, "-m", "silentos.vision_gate", str(raw_dir), str(model_path)]
    try:
        proc = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return False, f"Landmark extraction probe timed out after {PROBE_TIMEOUT_S:.0f}s"
    if proc.returncode == 0:
        return True, ""
    if proc.returncode < 0:
        return False, (
            f"Landmark extraction was killed outright (signal "
            f"{-proc.returncode}) on this host — known issue T-ML-01"
        )
    lines = (proc.stderr or proc.stdout or "").strip().splitlines()
    why = lines[-1] if lines else f"exit code {proc.returncode}"
    return False, f"Landmark extraction probe failed ({why})"


if __name__ == "__main__":  # pragma: no cover - child entry point
    sys.exit(_child(sys.argv[1], sys.argv[2]))
