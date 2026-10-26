/**
 * Typed API client for the SilentOS backend.
 * All requests go through this module — no raw fetch() in components.
 */

import type {
  AppStatus,
  CameraInfo,
  CameraStatus,
  ClipRecord,
  DatasetStats,
  DatasetSummary,
  SplitResult,
  ValidationReport,
  DiagnosticsReport,
  HealthResponse,
  HistoryPage,
  ModelInfo,
  ModelRegistryStatus,
  RecognitionStatus,
  SettingsUpdate,
  SettingsView,
  SystemMetrics,
  TrainingJobInfo,
} from "../types/api";

const BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 10_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(typeof init?.body === "string" ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "Request timed out");
    }
    throw new ApiError(0, "Backend unreachable");
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  status: () => request<AppStatus>("/status"),
  systemMetrics: () => request<SystemMetrics>("/system/metrics"),

  // settings
  getSettings: () => request<SettingsView>("/settings"),
  updateSettings: (body: SettingsUpdate) =>
    request<SettingsView>("/settings", { method: "PUT", body: JSON.stringify(body) }),

  // models
  models: () => request<ModelRegistryStatus>("/models"),
  model: (id: string) => request<ModelInfo>(`/models/${id}`),
  loadModel: (id: string) => request<{ detail: string }>(`/models/${id}/load`, { method: "POST" }),

  // recognition
  recognitionStatus: () => request<RecognitionStatus>("/recognition/status"),
  recognitionStart: () => request<{ runtime_state: string }>("/recognition/start", { method: "POST" }),
  recognitionStop: () => request<{ runtime_state: string }>("/recognition/stop", { method: "POST" }),
  history: (limit = 25, offset = 0) =>
    request<HistoryPage>(`/recognition/history?limit=${limit}&offset=${offset}`),
  clearHistory: () => request<{ cleared: number }>("/recognition/history", { method: "DELETE" }),

  // camera
  cameras: () => request<CameraInfo[]>("/cameras"),
  cameraStatus: () => request<CameraStatus>("/camera/status"),
  cameraCapabilities: () =>
    request<{ v4l2_devices: { device_path: string; name: string }[]; note: string }>(
      "/camera/capabilities",
    ),
  updateCameraConfig: (body: SettingsUpdate) =>
    request<SettingsView>("/camera/config", { method: "PUT", body: JSON.stringify(body) }),
  cameraStart: () => request<CameraStatus>("/camera/start", { method: "POST" }),
  cameraStop: () => request<CameraStatus>("/camera/stop", { method: "POST" }),

  // datasets
  datasets: () => request<DatasetSummary[]>("/datasets"),
  datasetStats: () => request<DatasetStats>("/datasets/stats"),
  recordClip: (body: { seconds: number; meta: Record<string, unknown> }) =>
    request<ClipRecord>("/datasets/record", { method: "POST", body: JSON.stringify(body) }),
  importClip: (form: FormData) =>
    request<ClipRecord>("/datasets/import", { method: "POST", body: form }, 60_000),
  validateDataset: (id: string) =>
    request<ValidationReport>(`/datasets/${id}/validate`, { method: "POST" }, 60_000),
  generateSplits: (id: string, body: { seed: number; train_ratio?: number; val_ratio?: number }) =>
    request<SplitResult>(`/datasets/${id}/splits`, { method: "POST", body: JSON.stringify(body) }),
  splitsStatus: (id: string) =>
    request<{ dataset_id: string; splits: Record<string, unknown> | null }>(
      `/datasets/${id}/splits`,
    ),
  exportUrl: (id: string, includeClips = true) =>
    `${BASE}/datasets/${id}/export?include_clips=${includeClips}`,

  // training
  trainingJobs: () => request<TrainingJobInfo[]>("/training/jobs"),
  trainingJob: (id: number) =>
    request<{ job: TrainingJobInfo; logs: unknown[] }>(`/training/jobs/${id}`),
  createTrainingJob: (body: { modality: string; dataset: string }) =>
    request<{ job?: TrainingJobInfo }>("/training/jobs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelTrainingJob: (id: number) =>
    request<{ status: string }>(`/training/jobs/${id}/cancel`, { method: "POST" }),

  // diagnostics
  dependencies: () => request<DiagnosticsReport>("/system/dependencies"),
  pythonInfo: () => request<{ version: string; executable: string; platform: string }>(
    "/system/python",
  ),
};
