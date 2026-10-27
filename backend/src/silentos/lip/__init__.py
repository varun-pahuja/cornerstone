"""Silent-lip recognition subsystem — Phase 6."""

from .features import FEATURE_DIM, MIN_FRAMES, NUM_LANDMARKS, SEQ_LEN, sequence_to_features
from .landmarks import FaceExtractor, LandmarkUnavailable
from .model import BaselineNotTrained, LogisticBaseline
from .pipeline import CONFIDENCE_FLOOR, LipRecognizer
from .train import TrainingError, train_lip, validate_request

__all__ = [
    "FEATURE_DIM",
    "MIN_FRAMES",
    "NUM_LANDMARKS",
    "SEQ_LEN",
    "sequence_to_features",
    "FaceExtractor",
    "LandmarkUnavailable",
    "BaselineNotTrained",
    "LogisticBaseline",
    "CONFIDENCE_FLOOR",
    "LipRecognizer",
    "TrainingError",
    "train_lip",
    "validate_request",
]
