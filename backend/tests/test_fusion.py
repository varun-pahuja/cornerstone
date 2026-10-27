"""Confidence-aware fusion engine tests — Phase 7."""

from __future__ import annotations

from silentos.fusion import FusionEngine, FusionPolicy, FusionWeights, fuse_predictions


def test_both_agree():
    d = fuse_predictions(
        {"label": "hello", "confidence": 0.9},
        {"label": "hello", "confidence": 0.7},
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.5, lip_threshold=0.5),
    )
    assert d.label == "hello"
    assert not d.abstained
    assert d.reason == "both_agree"
    assert d.sources == ["sign", "lip"]
    # 0.6*0.9 + 0.4*0.7 = 0.82
    assert abs(d.confidence - 0.82) < 1e-9


def test_disagree_sign_preferred():
    d = fuse_predictions(
        {"label": "a", "confidence": 0.9},
        {"label": "b", "confidence": 0.5},
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.4, lip_threshold=0.4),
    )
    assert d.label == "a"
    assert d.reason == "disagree_sign_preferred"
    assert abs(d.confidence - 0.54) < 1e-9  # 0.6*0.9


def test_disagree_lip_preferred():
    # sign=0.4 -> weighted 0.24; lip=0.95 -> weighted 0.38 (lip wins).
    # min_confidence must be <= 0.38 for this to be accepted, not abstained.
    d = fuse_predictions(
        {"label": "a", "confidence": 0.4},
        {"label": "b", "confidence": 0.95},
        policy=FusionPolicy(min_confidence=0.35, sign_threshold=0.3, lip_threshold=0.3),
    )
    assert d.label == "b"
    assert d.reason == "disagree_lip_preferred"
    assert abs(d.confidence - 0.38) < 1e-9  # 0.4*0.95


def test_single_modality_disabled():
    d = fuse_predictions(
        {"label": "a", "confidence": 0.9},
        None,
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.4, allow_single_modality=False),
    )
    assert d.abstained
    assert d.reason == "single_modality_disabled"
    assert d.label is None


def test_single_modality_below_min():
    d = fuse_predictions(
        {"label": "a", "confidence": 0.55},
        None,
        policy=FusionPolicy(min_confidence=0.6, sign_threshold=0.4, allow_single_modality=True),
    )
    assert d.abstained
    assert d.reason == "below_min_confidence"
    assert d.label is None


def test_no_modality_above_threshold():
    d = fuse_predictions(
        {"label": "a", "confidence": 0.3},
        {"label": "b", "confidence": 0.2},
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.4, lip_threshold=0.4),
    )
    assert d.abstained
    assert d.reason == "no_modality_above_threshold"
    assert d.label is None
    assert d.confidence == 0.0
    assert d.sources == []


def test_both_present_but_both_below_threshold():
    d = fuse_predictions(
        {"label": "a", "confidence": 0.3},
        {"label": "b", "confidence": 0.35},
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.4, lip_threshold=0.4),
    )
    assert d.abstained
    assert d.reason == "no_modality_above_threshold"


def test_engine_class_delegates():
    eng = FusionEngine(
        weights=FusionWeights(sign=0.6, lip=0.4),
        policy=FusionPolicy(min_confidence=0.5, sign_threshold=0.4, lip_threshold=0.4),
    )
    d = eng.fuse({"label": "x", "confidence": 0.8}, {"label": "x", "confidence": 0.6})
    assert d.label == "x"
    assert not d.abstained


def test_weights_normalized():
    w = FusionWeights(sign=0.8, lip=0.2)
    assert abs(w.sign + w.lip - 1.0) < 1e-9
    assert abs(w.sign - 0.8) < 1e-9


def test_both_agree_below_min():
    d = fuse_predictions(
        {"label": "hello", "confidence": 0.55},
        {"label": "hello", "confidence": 0.55},
        policy=FusionPolicy(min_confidence=0.6, sign_threshold=0.4, lip_threshold=0.4),
    )
    # 0.6*0.55 + 0.4*0.55 = 0.55 < 0.6 -> abstain
    assert d.abstained
    assert d.label is None
    assert d.reason == "below_min_confidence"
    assert abs(d.confidence - 0.55) < 1e-9
