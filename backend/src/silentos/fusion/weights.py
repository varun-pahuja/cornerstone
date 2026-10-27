"""Fusion weights (config-driven defaults, pure data)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionWeights:
    sign: float = 0.6
    lip: float = 0.4

    def __post_init__(self) -> None:
        total = self.sign + self.lip
        if total <= 0:
            raise ValueError("fusion weights must sum to > 0")
        # Normalize to sum to 1.0 (keep deterministic)
        object.__setattr__(self, "sign", self.sign / total)
        object.__setattr__(self, "lip", self.lip / total)
