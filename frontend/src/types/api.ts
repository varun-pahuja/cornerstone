/**
 * API types — mirror of the backend Pydantic schemas (schemas.py).
 * Keep in sync: schema_version "1.0".
 */

export const SCHEMA_VERSION = "1.0";

export type RuntimeState = "STOPPED" | "STARTING" | "RUNNING" | "STOPPING" | "ERROR";
export type CameraState = "DISCONNECTED" | "CONNECTING" | "CONNECTED" | "ERROR" | "UNAVAILABLE";
export type ModelStatus =
  | "LOADED"
  | "NOT_LOADED"
  | "ERROR"
  | "NOT_TRAINED";
export type RecognitionMode = "sign" | "lip" | "both";
export type CameraProvider =
  | "video_file"
  | "mock"
  | "development_webcam"
  | "pi_camera"
  | "pi_usb_webcam";

export interface HealthResponse {
  status: string;
  version: string;
  schema_version: string;
  timestamp: string;
}

export interface SystemMetrics {
  cpu_percent: number | null;
  memory_percent: number | null;
  memory_used_mb: number | null;
  memory_total_mb: number | null;
  disk_percent: number | null;
  temperature_c: number | null;
  hostname: string | null;
  platform: string | null;
  timestamp: string;
}

export interface AppStatus {
  runtime_state: RuntimeState;
  recognition_mode: RecognitionMode;
  camera_state: CameraState;
  camera_provider: CameraProvider | string;
  sign_model_status: ModelStatus;
  lip_model_status: ModelStatus;
  speech_enabled: boolean;
  last_message: string | null;
  last_recognition: Record<string, unknown> | null;
  inference_latency_ms: number | null;
  schema_version: string;
  timestamp: string;
}

export interface CameraInfo {
  provider: string;
  label: string;
  device_path: string | null;
  connected: boolean;
  width: number | null;
  height: number | null;
  fps: number | null;
}

export interface CameraStatus {
  state: CameraState;
  provider: string;
  width: number | null;
  height: number | null;
  fps: number | null;
  frames_captured: number;
  last_frame_age_ms: number | null;
  error: string | null;
}

export interface ModelInfo {
  model_id: string;
  modality: string;
  version: string;
  status: ModelStatus;
  path: string | null;
  labels: string[] | null;
  input_shape: number[] | null;
  preprocessing_version: string | null;
  evaluation: Record<string, unknown> | null;
  error: string | null;
}
