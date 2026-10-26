"""Pydantic schemas shared across the API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class RuntimeState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class CameraState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class ModelStatus(str, Enum):
    LOADED = "LOADED"
    NOT_LOADED = "NOT_LOADED"
    ERROR = "ERROR"
    NOT_TRAINED = "NOT_TRAINED"


class RecognitionMode(str, Enum):
    SIGN = "sign"
    LIP = "lip"
    BOTH = "both"


# ---- Health / Status ----

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime


class SystemMetrics(BaseModel):
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    disk_percent: float | None = None
    temperature_c: float | None = None
    hostname: str | None = None
    platform: str | None = None
    timestamp: datetime


class AppStatus(BaseModel):
    runtime_state: RuntimeState
    recognition_mode: RecognitionMode
    camera_state: CameraState
    camera_provider: str
    sign_model_status: ModelStatus
    lip_model_status: ModelStatus
    speech_enabled: bool
    last_message: str | None = None
    last_recognition: dict[str, Any] | None = None
    inference_latency_ms: float | None = None
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime


# ---- Camera ----

class CameraInfo(BaseModel):
    provider: str
    label: str
    device_path: str | None = None
    available: bool = True
    detail: str | None = None
    connected: bool = False
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class CameraStatus(BaseModel):
    state: CameraState
    provider: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames_captured: int = 0
    frames_dropped: int = 0
    last_frame_age_ms: float | None = None
    error: str | None = None


class CameraConfigUpdate(BaseModel):
    provider: str | None = None
    target_width: int | None = Field(default=None, ge=64, le=3840)
    target_height: int | None = Field(default=None, ge=64, le=2160)
    target_fps: float | None = Field(default=None, ge=1.0, le=60.0)
    video_path: str | None = None
    device_index: int | None = Field(default=None, ge=0, le=16)


# ---- Recognition ----

class ModalityPrediction(BaseModel):
    modality: str
    predicted_class: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    probabilities: dict[str, float] | None = None
    timestamp: datetime
    model_version: str | None = None
    processing_latency_ms: float | None = None
    status: ModelStatus


class FusionDecision(BaseModel):
    final_label: str
    accepted: bool
    reason: str
    sign_prediction: ModalityPrediction | None = None
    lip_prediction: ModalityPrediction | None = None
    timestamp: datetime
    schema_version: str = SCHEMA_VERSION


class RecognitionEvent(BaseModel):
    id: int
    timestamp: datetime
    mode: RecognitionMode
    sign_label: str | None = None
    sign_confidence: float | None = None
    lip_label: str | None = None
    lip_confidence: float | None = None
    final_label: str
    accepted: bool
    reason: str
    latency_ms: float | None = None


class RecognitionStatus(BaseModel):
    runtime_state: RuntimeState
    mode: RecognitionMode
    sign_model: ModelStatus
    lip_model: ModelStatus
    frames_processed: int = 0
    last_decision: FusionDecision | None = None
    latency_ms: float | None = None


# ---- Models ----

class ModelInfo(BaseModel):
    model_id: str
    modality: str
    version: str
    status: ModelStatus
    path: str | None = None
    labels: list[str] | None = None
    input_shape: list[int] | None = None
    preprocessing_version: str | None = None
    evaluation: dict[str, Any] | None = None
    error: str | None = None


# ---- WebSocket events ----

class WsEvent(BaseModel):
    type: str
    payload: dict[str, Any]
    timestamp: datetime
    schema_version: str = SCHEMA_VERSION


# ---- Settings ----

class SettingsView(BaseModel):
    """Effective runtime settings returned to the dashboard."""

    recognition_mode: RecognitionMode
    min_confidence: float
    sign_threshold: float
    lip_threshold: float
    allow_single_modality: bool
    speech_enabled: bool
    speech_cooldown_ms: int
    history_retention_days: int
    history_max_entries: int
    camera_provider: str
    camera_target_width: int
    camera_target_height: int
    camera_target_fps: float
    camera_video_path: str | None = None
    camera_device_index: int
    vocabulary: list[str]
    abstain_label: str
    requires_restart: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    """Partial update. None = leave unchanged."""

    recognition_mode: RecognitionMode | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sign_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    lip_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    allow_single_modality: bool | None = None
    speech_enabled: bool | None = None
    speech_cooldown_ms: int | None = Field(default=None, ge=0, le=60000)
    history_retention_days: int | None = Field(default=None, ge=1, le=3650)
    history_max_entries: int | None = Field(default=None, ge=100, le=1_000_000)
    camera_provider: str | None = None
    camera_target_width: int | None = Field(default=None, ge=64, le=3840)
    camera_target_height: int | None = Field(default=None, ge=64, le=2160)
    camera_target_fps: float | None = Field(default=None, ge=0.1, le=60.0)
    camera_video_path: str | None = None
    camera_device_index: int | None = Field(default=None, ge=0, le=16)


# ---- Models ----

class ModelRegistryStatus(BaseModel):
    models: list[ModelInfo]
    sign_status: ModelStatus
    lip_status: ModelStatus


# ---- Datasets ----

class DatasetSummary(BaseModel):
    dataset_id: str
    name: str
    clip_count: int
    path: str


class DatasetStats(BaseModel):
    total_clips: int = 0
    raw_video_files: int = 0
    manifests: int = 0
    by_class: dict[str, int] = Field(default_factory=dict)
    by_modality: dict[str, int] = Field(default_factory=dict)
    by_split: dict[str, int] = Field(default_factory=dict)


# ---- Training ----

class TrainingJobInfo(BaseModel):
    id: int
    created_at: str
    modality: str
    dataset: str
    status: str
    progress: float
    current_epoch: int
    total_epochs: int
    metrics: dict[str, Any] | None = None
    error: str | None = None


class TrainingJobCreate(BaseModel):
    modality: str = Field(pattern="^(sign|lip)$")
    dataset: str = Field(min_length=1, max_length=200)
    config: dict[str, Any] = Field(default_factory=dict)


# ---- Diagnostics ----

class DependencyCheck(BaseModel):
    name: str
    kind: str            # "python" | "binary"
    available: bool
    version: str | None = None
    required_for: str


class DiagnosticsReport(BaseModel):
    dependencies: list[DependencyCheck]
    offline_ok: bool
    notes: list[str] = Field(default_factory=list)
    timestamp: datetime


# ---- Dataset engine (Phase 4) ----

class ClipMeta(BaseModel):
    """Metadata required to register/record a clip."""

    label: str = Field(min_length=1, max_length=64)
    modality: Literal["sign", "lip"]
    participant_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    lighting: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=500)
    dataset_id: str = Field(default="default", pattern=r"^[A-Za-z0-9_-]{1,64}$")


class ClipRecord(BaseModel):
    clip_id: str
    dataset_id: str
    file: str                 # path relative to data root
    label: str
    modality: str
    participant_id: str
    session_id: str
    lighting: str | None = None
    notes: str | None = None
    duration_s: float
    frames: int
    width: int
    height: int
    fps: float
    sha256: str
    split: str | None = None
    created_at: str


class ValidationIssue(BaseModel):
    clip_id: str
    file: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    dataset_id: str
    checked: int
    valid: int
    invalid: int
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked_at: datetime


class DatasetManifest(BaseModel):
    dataset_id: str
    name: str
    created_at: str
    updated_at: str
    clip_count: int
    clips: list[ClipRecord]
    splits: dict[str, Any] | None = None


class SplitRequest(BaseModel):
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    train_ratio: float = Field(default=0.70, gt=0.0, lt=1.0)
    val_ratio: float = Field(default=0.15, gt=0.0, lt=1.0)
    # test_ratio = 1 - train - val (validated in the endpoint)


class SplitResult(BaseModel):
    dataset_id: str
    seed: int
    ratios: dict[str, float]
    participants: dict[str, str]   # participant_id -> split name
    clip_counts: dict[str, int]
    warnings: list[str] = Field(default_factory=list)


class RecordRequest(BaseModel):
    seconds: float = Field(default=3.0, ge=0.5, le=10.0)
    meta: ClipMeta
