"""T-ML-01 bounded diagnostic probe (run exactly once under gdb).

Reproduces the shape of the 2026-10-30 probe 4 that died between extractions
~21 and ~24: stream frames from one real ISL clip, extract every step-th frame,
print with flush=True after each extraction, exit 0 only on full survival.

Invoked directly (no pipeline), so the shell captures the true exit status.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "backend" / "src"))

import cv2  # noqa: E402

from silentos.sign.landmarks import HandExtractor  # noqa: E402


def rss_mb() -> int:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) // 1024
    return -1


def main() -> int:
    clips = sorted((REPO / "data" / "raw").rglob("*.mp4"))
    cand = [c for c in clips if c.parts[-2].startswith("User")] or clips
    clip = cand[0]
    print(f"clip={clip.name}", flush=True)

    cap = cv2.VideoCapture(str(clip))
    # count frames first (streamed, not buffered)
    n_total = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n_total += 1
    cap.release()
    step = max(1, n_total // 30)
    print(f"frames={n_total} step={step} start_rss_mb={rss_mb()}", flush=True)

    ex = HandExtractor(REPO / "models" / "assets" / "hand_landmarker.task")
    cap = cv2.VideoCapture(str(clip))
    t0 = time.time()
    i = 0
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            lm = ex.extract(frame)
            n += 1
            print(
                f"extract n={n} idx={i} hand={'Y' if lm is not None else 'N'} "
                f"rss_mb={rss_mb()} elapsed_s={time.time() - t0:.2f}",
                flush=True,
            )
        i += 1
    cap.release()
    print(f"SURVIVED n={n} final_rss_mb={rss_mb()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
