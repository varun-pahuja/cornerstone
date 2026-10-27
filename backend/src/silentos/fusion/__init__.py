"""Confidence-aware fusion for sign and silent-lip predictions — Phase 7."""

from .engine import FusionEngine, fuse_predictions
from .policy import FusionPolicy
from .weights import FusionWeights

__all__ = ["FusionEngine", "fuse_predictions", "FusionPolicy", "FusionWeights"]
