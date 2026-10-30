"""Calibration engine tests — Phase 9."""

from __future__ import annotations

from silentos.calibration import compute_profile


def _row(final, sc=None, lc=None):
    return {
        "final_label": final,
        "sign_label": "x" if sc is not None else None,
        "sign_confidence": sc,
        "lip_label": "x" if lc is not None else None,
        "lip_confidence": lc,
    }


def test_empty_history_not_calibrated():
    p = compute_profile([], fallback_sign=0.6, fallback_lip=0.6, fallback_min=0.6)
    assert not p.calibrated
    assert p.samples == 0
    assert "No recorded history" in (p.shortfall or "")


def test_insufficient_samples_reports_shortfall():
    rows = [_row("hello", sc=0.7), _row("hello", sc=0.8)]
    p = compute_profile(rows, fallback_sign=0.6, fallback_lip=0.6, fallback_min=0.6)
    assert not p.calibrated
    assert p.samples == 2
    assert "Need at least 5" in (p.shortfall or "")
    # Fallbacks preserved, not fabricated
    assert p.sign_threshold == 0.6
    assert p.lip_threshold == 0.6


def test_enough_samples_computes_thresholds():
    rows = [_row("hello", sc=c) for c in [0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85]]
    p = compute_profile(rows, fallback_sign=0.6, fallback_lip=0.6, fallback_min=0.6)
    assert p.calibrated
    assert p.samples == 7
    # 25th percentile of [0.55..0.85] ~ 0.6
    assert 0.5 <= p.sign_threshold <= 0.7
    assert p.computed_at is not None
    assert "hello" in p.classes
    assert "hello" in p.per_class_mean_confidence


def test_to_dict_serializable():
    p = compute_profile([], fallback_sign=0.6, fallback_lip=0.6, fallback_min=0.6)
    d = p.to_dict()
    assert d["calibrated"] is False
    assert d["samples"] == 0
    assert d["computed_at"] is None
