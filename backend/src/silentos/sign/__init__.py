"""Sign (gesture) recognition subsystem — Phases 5."""

from .features import FEATURE_DIM, MIN_FRAMES, NUM_LANDMARKS, SEQ_LEN, sequence_to_features
from .landmarks import HandExtractor, LandmarkUnavailable
from .model import BaselineNotTrained, LogisticBaseline
from .pipeline import CONFIDENCE_FLOOR, SignRecognizer
from .train import TrainingError, train_sign, validate_request

__all__ = [
    "FEATURE_DIM",
    "MIN_FRAMES",
    "NUM_LANDMARKS",
    "SEQ_LEN",
    "sequence_to_features",
    "HandExtractor",
    "LandmarkUnavailable",
    "BaselineNotTrained",
    "LogisticBaseline",
    "CONFIDENCE_FLOOR",
    "SignRecognizer",
    "TrainingError",
    "train_sign",
    "validate_request",
]
