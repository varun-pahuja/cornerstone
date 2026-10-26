"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_VOCABULARY = [
    "HELP", "WATER", "FOOD", "PAIN", "YES",
    "NO", "STOP", "DOCTOR", "TOILET", "THANK YOU",
]


class ApiConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000


class PathsConfig(BaseModel):
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./models")
    raw_dir: Path = Path("./data/raw")
    processed_dir: Path = Path("./data/processed")
    annotations_dir: Path = Path("./data/annotations")
    manifests_dir: Path = Path("./data/manifests")
    splits_dir: Path = Path("./data/splits")

    @classmethod
    def rooted(cls, root: Path) -> "PathsConfig":
        """Build a fully isolated path set under `root` (used by tests)."""
        data = root / "data"
        return cls(
            data_dir=data,
            models_dir=root / "models",
            raw_dir=data / "raw",
            processed_dir=data / "processed",
            annotations_dir=data / "annotations",
            manifests_dir=data / "manifests",
            splits_dir=data / "splits",
        )

    def ensure(self) -> None:
        for p in (self.data_dir, self.models_dir, self.raw_dir,
                  self.processed_dir, self.annotations_dir,
                  self.manifests_dir, self.splits_dir):
            p.mkdir(parents=True, exist_ok=True)


class VocabularyConfig(BaseModel):
    labels: list[str] = Field(default_factory=lambda: list(DEFAULT_VOCABULARY))
    abstain_label: str = "PLEASE REPEAT"

    @field_validator("labels")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("vocabulary must have at least 2 labels")
        if len(set(v)) != len(v):
            raise ValueError("vocabulary labels must be unique")
        return v


class CameraConfig(BaseModel):
    provider: Literal[
        "video_file", "mock", "development_webcam", "pi_camera", "pi_usb_webcam"
    ] = "video_file"
    target_width: int = Field(default=640, ge=64, le=3840)
    target_height: int = Field(default=480, ge=64, le=2160)
    target_fps: float = Field(default=15.0, ge=1.0, le=60.0)
    video_path: str | None = None
    device_index: int = Field(default=0, ge=0, le=16)
    frame_queue_size: int = Field(default=4, ge=1, le=32)


class RecognitionConfig(BaseModel):
    mode: Literal["sign", "lip", "both"] = "both"
    sequence_length: int = Field(default=16, ge=2, le=128)
    inference_interval_ms: int = Field(default=200, ge=16, le=5000)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class FusionConfig(BaseModel):
    sign_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    lip_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    allow_single_modality: bool = False
    max_prediction_age_ms: int = Field(default=1500, ge=50, le=60000)
    decision_cooldown_ms: int = Field(default=1500, ge=0, le=60000)


class OutputConfig(BaseModel):
    speech_enabled: bool = False
    speech_cooldown_ms: int = Field(default=3000, ge=0, le=60000)
    history_retention_days: int = Field(default=30, ge=1, le=3650)
    history_max_entries: int = Field(default=10000, ge=100, le=1_000_000)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    max_bytes: int = 1_048_576
    backup_count: int = 3


class AppConfig(BaseModel):
    name: str = "SilentOS"
    env: Literal["development", "production", "test"] = "production"


class Settings(BaseModel):
    """Root settings loaded from a YAML file with defaults."""

    app: AppConfig = AppConfig()
    api: ApiConfig = ApiConfig()
    paths: PathsConfig = PathsConfig()
    vocabulary: VocabularyConfig = VocabularyConfig()
    camera: CameraConfig = CameraConfig()
    recognition: RecognitionConfig = RecognitionConfig()
    fusion: FusionConfig = FusionConfig()
    output: OutputConfig = OutputConfig()
    logging: LoggingConfig = LoggingConfig()


def load_settings(path: str | Path | None = None) -> Settings:
    """Load settings from YAML, falling back to defaults.

    A provided path that does not exist raises FileNotFoundError.
    When path is None, defaults are returned.
    """
    if path is None:
        return Settings()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p}")
    with p.open() as f:
        raw = yaml.safe_load(f) or {}
    return Settings.model_validate(raw)
