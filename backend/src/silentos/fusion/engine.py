"""Confidence-aware fusion engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .policy import FusionPolicy
from .weights import FusionWeights


@dataclass(frozen=True)
class FusionDecision:
    label: str | None
    confidence: float
    sources: list[str]
    abstained: bool
    reason: str
    scores: dict[str, float]


class FusionEngine:
    def __init__(self, weights: FusionWeights | None = None, policy: FusionPolicy | None = None):
        self.weights = weights or FusionWeights()
        self.policy = policy or FusionPolicy()

    def fuse(self, sign: dict[str, Any] | None, lip: dict[str, Any] | None) -> FusionDecision:
        return fuse_predictions(sign, lip, self.weights, self.policy)


def fuse_predictions(
    sign: dict[str, Any] | None,
    lip: dict[str, Any] | None,
    weights: FusionWeights | None = None,
    policy: FusionPolicy | None = None,
) -> FusionDecision:
    weights = weights or FusionWeights()
    policy = policy or FusionPolicy()

    sp = None
    if sign and sign.get("label") and float(sign.get("confidence", 0)) >= policy.sign_threshold:
        sp = (str(sign["label"]), float(sign["confidence"]))

    lp = None
    if lip and lip.get("label") and float(lip.get("confidence", 0)) >= policy.lip_threshold:
        lp = (str(lip["label"]), float(lip["confidence"]))

    if sp is None and lp is None:
        return FusionDecision(label=None, confidence=0.0, sources=[], abstained=True, reason="no_modality_above_threshold", scores={})

    if sp is not None and lp is None:
        if not policy.allow_single_modality:
            return FusionDecision(label=None, confidence=sp[1], sources=["sign"], abstained=True, reason="single_modality_disabled", scores={sp[0]: sp[1]})
        if sp[1] < policy.min_confidence:
            return FusionDecision(label=None, confidence=sp[1], sources=["sign"], abstained=True, reason="below_min_confidence", scores={sp[0]: sp[1]})
        return FusionDecision(label=sp[0], confidence=sp[1], sources=["sign"], abstained=False, reason="single_sign", scores={sp[0]: sp[1]})

    if lp is not None and sp is None:
        if not policy.allow_single_modality:
            return FusionDecision(label=None, confidence=lp[1], sources=["lip"], abstained=True, reason="single_modality_disabled", scores={lp[0]: lp[1]})
        if lp[1] < policy.min_confidence:
            return FusionDecision(label=None, confidence=lp[1], sources=["lip"], abstained=True, reason="below_min_confidence", scores={lp[0]: lp[1]})
        return FusionDecision(label=lp[0], confidence=lp[1], sources=["lip"], abstained=False, reason="single_lip", scores={lp[0]: lp[1]})

    # both present
    s_label, s_conf = sp  # type: ignore
    l_label, l_conf = lp  # type: ignore
    if s_label == l_label:
        conf = weights.sign * s_conf + weights.lip * l_conf
        if conf < policy.min_confidence:
            return FusionDecision(label=None, confidence=conf, sources=["sign", "lip"], abstained=True, reason="below_min_confidence", scores={s_label: conf})
        return FusionDecision(label=s_label, confidence=conf, sources=["sign", "lip"], abstained=False, reason="both_agree", scores={s_label: conf})
    # disagree — pick higher weighted score
    s_score = weights.sign * s_conf
    l_score = weights.lip * l_conf
    if s_score >= l_score:
        conf = s_score
        if conf < policy.min_confidence:
            return FusionDecision(label=None, confidence=conf, sources=["sign", "lip"], abstained=True, reason="disagree_below_min_confidence", scores={s_label: s_score, l_label: l_score})
        return FusionDecision(label=s_label, confidence=conf, sources=["sign", "lip"], abstained=False, reason="disagree_sign_preferred", scores={s_label: s_score, l_label: l_score})
    conf = l_score
    if conf < policy.min_confidence:
        return FusionDecision(label=None, confidence=conf, sources=["sign", "lip"], abstained=True, reason="disagree_below_min_confidence", scores={s_label: s_score, l_label: l_score})
    return FusionDecision(label=l_label, confidence=conf, sources=["sign", "lip"], abstained=False, reason="disagree_lip_preferred", scores={s_label: s_score, l_label: l_score})
