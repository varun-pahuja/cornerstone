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
  available: boolean;
  detail: string | null;
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
  frames_dropped: number;
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

// ---- Phase 2 additions ----

export interface SettingsView {
  recognition_mode: RecognitionMode;
  min_confidence: number;
  sign_threshold: number;
  lip_threshold: number;
  allow_single_modality: boolean;
  speech_enabled: boolean;
  speech_cooldown_ms: number;
  history_retention_days: number;
  history_max_entries: number;
  camera_provider: string;
  camera_target_width: number;
  camera_target_height: number;
  camera_target_fps: number;
  camera_video_path: string | null;
  camera_device_index: number;
  vocabulary: string[];
  abstain_label: string;
  requires_restart: string[];
}

export interface SettingsUpdate {
  recognition_mode?: RecognitionMode;
  min_confidence?: number;
  sign_threshold?: number;
  lip_threshold?: number;
  allow_single_modality?: boolean;
  speech_enabled?: boolean;
  speech_cooldown_ms?: number;
  history_retention_days?: number;
  history_max_entries?: number;
  camera_provider?: string;
  camera_target_width?: number;
  camera_target_height?: number;
  camera_target_fps?: number;
  camera_video_path?: string | null;
  camera_device_index?: number;
}

export interface ModelRegistryStatus {
  models: ModelInfo[];
  sign_status: ModelStatus;
  lip_status: ModelStatus;
}

export interface DatasetSummary {
  dataset_id: string;
  name: string;
  clip_count: number;
  path: string;
}

export interface DatasetStats {
  total_clips: number;
  raw_video_files: number;
  manifests: number;
  by_class: Record<string, number>;
  by_modality: Record<string, number>;
  by_split: Record<string, number>;
}

export interface TrainingJobInfo {
  id: number;
  created_at: string;
  modality: string;
  dataset: string;
  status: string;
  progress: number;
  current_epoch: number;
  total_epochs: number;
  metrics: Record<string, unknown> | null;
  error: string | null;
}

export interface DependencyCheck {
  name: string;
  kind: "python" | "binary";
  available: boolean;
  version: string | null;
  required_for: string;
}

export interface DiagnosticsReport {
  dependencies: DependencyCheck[];
  offline_ok: boolean;
  notes: string[];
  timestamp: string;
}

export interface HistoryItem {
  id: number;
  timestamp: string;
  mode: string;
  sign_label: string | null;
  sign_confidence: number | null;
  lip_label: string | null;
  lip_confidence: number | null;
  final_label: string;
  accepted: boolean;
  reason: string;
  latency_ms: number | null;
}

export interface HistoryPage {
  items: HistoryItem[];
  total: number;
}

export interface RecognitionStatus {
  runtime_state: RuntimeState;
  mode: RecognitionMode;
  sign_model: ModelStatus;
  lip_model: ModelStatus;
  frames_processed: number;
  last_decision: Record<string, unknown> | null;
  latency_ms: number | null;
}

export interface ClipRecord {
  clip_id: string;
  dataset_id: string;
  file: string;
  label: string;
  modality: string;
  participant_id: string;
  session_id: string;
  lighting: string | null;
  notes: string | null;
  duration_s: number;
  frames: number;
  width: number;
  height: number;
  fps: number;
  sha256: string;
  split: string | null;
  created_at: string;
}

export interface ValidationIssue {
  clip_id: string;
  file: string;
  errors: string[];
  warnings: string[];
}

export interface ValidationReport {
  dataset_id: string;
  checked: number;
  valid: number;
  invalid: number;
  issues: ValidationIssue[];
  checked_at: string;
}

export interface SplitResult {
  dataset_id: string;
  seed: number;
  ratios: Record<string, number>;
  participants: Record<string, string>;
  clip_counts: Record<string, number>;
  warnings: string[];
}
