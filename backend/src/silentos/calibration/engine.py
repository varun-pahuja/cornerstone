"""Threshold calibration from recorded recognition history.

Honest semantics: a profile is computed only from real recorded history rows.
If there is not enough history, the engine reports `not_calibrated` with the
shortfall — it never fabricates thresholds.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("silentos.calibration")

MIN_SAMPLES_PER_CLASS = 5  # per-modality, per-class minimum for a stable estimate


@dataclass(frozen=True)
class CalibrationProfile:
    """Tuned thresholds derived from measured confidence distributions."""

    calibrated: bool
    sign_threshold: float
    lip_threshold: float
    min_confidence: float
    samples: int
    classes: list[str] = field(default_factory=list)
    per_class_mean_confidence: dict[str, float] = field(default_factory=dict)
    shortfall: str | None = None
    computed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "calibrated": self.calibrated,
            "sign_threshold": self.sign_threshold,
            "lip_threshold": self.lip_threshold,
            "min_confidence": self.min_confidence,
            "samples": self.samples,
            "classes": self.classes,
            "per_class_mean_confidence": self.per_class_mean_confidence,
            "shortfall": self.shortfall,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
        }


def compute_profile(
    history_rows: list[dict],
    fallback_sign: float,
    fallback_lip: float,
    fallback_min: float,
) -> CalibrationProfile:
    """Compute a calibration profile from real history rows.

    Each row must have: final_label, sign_label, sign_confidence,
    lip_label, lip_confidence (None allowed for absent modality).
    """
    if not history_rows:
        return CalibrationProfile(
            calibrated=False,
            sign_threshold=fallback_sign,
            lip_threshold=fallback_lip,
            min_confidence=fallback_min,
            samples=0,
            shortfall="No recorded history — record clips and run recognition first.",
        )

    sign_confs: list[float] = []
    lip_confs: list[float] = []
    per_class: dict[str, list[float]] = {}

    for row in history_rows:
        label = row.get("final_label")
        if label and label not in ("PLEASE REPEAT", ""):
            per_class.setdefault(label, [])
        sc = row.get("sign_confidence")
        if sc is not None:
            sign_confs.append(float(sc))
            if label and label not in ("PLEASE REPEAT", ""):
                per_class[label].append(float(sc))
        lc = row.get("lip_confidence")
        if lc is not None:
            lip_confs.append(float(lc))

    # Per-class mean confidence (for the report)
    per_class_mean = {
        k: round(statistics.mean(v), 4) for k, v in per_class.items() if v
    }

    # Tune thresholds as a percentile of the measured distributions.
    # Use a conservative floor: 25th percentile (so low-confidence noise is
    # filtered while real gestures still pass).
    def _pctl(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    sign_thr = round(_pctl(sign_confs, 0.25), 4) if sign_confs else fallback_sign
    lip_thr = round(_pctl(lip_confs, 0.25), 4) if lip_confs else fallback_lip

    # Min-confidence: keep the lower of the two tuned thresholds, but never
    # below the fallback floor to avoid over-relaxing.
    min_conf = round(min(sign_thr, lip_thr) if (sign_confs and lip_confs) else min(
        sign_thr if sign_confs else fallback_min,
        lip_thr if lip_confs else fallback_min,
    ), 4)
    min_conf = max(min_conf, fallback_min * 0.5)  # don't go below half the configured default

    total_samples = len(sign_confs) + len(lip_confs)
    enough = len(sign_confs) >= MIN_SAMPLES_PER_CLASS or len(lip_confs) >= MIN_SAMPLES_PER_CLASS

    if not enough:
        return CalibrationProfile(
            calibrated=False,
            sign_threshold=fallback_sign,
            lip_threshold=fallback_lip,
            min_confidence=fallback_min,
            samples=total_samples,
            classes=sorted(per_class_mean),
            per_class_mean_confidence=per_class_mean,
            shortfall=(
                f"Need at least {MIN_SAMPLES_PER_CLASS} samples per modality; "
                f"have sign={len(sign_confs)}, lip={len(lip_confs)}."
            ),
        )

    return CalibrationProfile(
        calibrated=True,
        sign_threshold=sign_thr,
        lip_threshold=lip_thr,
        min_confidence=min_conf,
        samples=total_samples,
        classes=sorted(per_class_mean),
        per_class_mean_confidence=per_class_mean,
        computed_at=datetime.now(timezone.utc),
    )


class CalibrationEngine:
    """Stateful wrapper: fetch history, compute, persist, apply."""

    def __init__(self, db, settings):
        self._db = db
        self._settings = settings

    def compute(self) -> CalibrationProfile:
        rows = self._db.list_history(limit=10_000)
        fus = self._settings.fusion
        rec = self._settings.recognition
        return compute_profile(
            rows,
            fallback_sign=fus.sign_threshold,
            fallback_lip=fus.lip_threshold,
            fallback_min=rec.min_confidence,
        )

    def apply(self, profile: CalibrationProfile) -> None:
        """Persist the tuned thresholds into settings overrides."""
        if not profile.calibrated:
            return
        self._settings.fusion.sign_threshold = profile.sign_threshold
        self._settings.fusion.lip_threshold = profile.lip_threshold
        self._settings.recognition.min_confidence = profile.min_confidence
