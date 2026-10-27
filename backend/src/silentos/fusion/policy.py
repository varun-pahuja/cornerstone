"""Decision policy: thresholds, abstain, single-modality rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionPolicy:
    min_confidence: float = 0.45
    sign_threshold: float = 0.45
    lip_threshold: float = 0.45
    allow_single_modality: bool = True
    require_agreement_boost: bool = False

    def __post_init__(self) -> None:
        for name, v in (
            ("min_confidence", self.min_confidence),
            ("sign_threshold", self.sign_threshold),
            ("lip_threshold", self.lip_threshold),
        ):
            if not 0.0 <= float(v) <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
