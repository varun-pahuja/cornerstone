"""Offline speech output via espeak-ng (Phase 8).

Honest semantics: if espeak-ng is not on PATH, the engine reports unavailable
and `speak` is a no-op — never fabricate audio or pretend to speak.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time

logger = logging.getLogger("silentos.output")


class SpeechEngine:
    """Cooldown-aware text-to-speech wrapper around espeak-ng.

    Thread-safe: `speak` can be called from the recognition loop.
    """

    def __init__(self, cooldown_ms: int = 3000, binary: str = "espeak-ng"):
        self._binary = binary
        self._cooldown_s = max(0, cooldown_ms) / 1000.0
        self._lock = threading.Lock()
        self._last_spoken_monotonic: float | None = None

    @property
    def available(self) -> bool:
        return shutil.which(self._binary) is not None

    def speak(self, text: str, force: bool = False) -> bool:
        """Speak `text` if cooldown elapsed (or `force`). Returns True if spoken."""
        if not text or not self.available:
            return False
        now = time.monotonic()
        with self._lock:
            if (
                not force
                and self._last_spoken_monotonic is not None
                and (now - self._last_spoken_monotonic) < self._cooldown_s
            ):
                return False
            self._last_spoken_monotonic = now
        try:
            # -x: keep it simple; espeak-ng writes to default audio device.
            subprocess.run(
                [self._binary, text],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return True
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning("espeak-ng failed: %s", e)
            return False

    def reset_cooldown(self) -> None:
        with self._lock:
            self._last_spoken_monotonic = None


def speak_decision(
    engine: SpeechEngine, label: str | None, abstain_label: str, enabled: bool
) -> bool:
    """Speak a fused decision's label if accepted and speech is enabled."""
    if not enabled or label is None:
        return False
    if label == abstain_label:
        return False
    return engine.speak(label)
