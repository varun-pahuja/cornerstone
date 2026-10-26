"""Pydantic schemas shared across the API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

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
