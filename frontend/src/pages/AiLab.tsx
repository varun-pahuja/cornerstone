import { useState } from "react";
import { Cpu, Upload } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { ModelInfo, ModelStatus } from "../types/api";

const statusTone: Record<ModelStatus, "ok" | "warn" | "danger" | "neutral"> = {
  LOADED: "ok",
  NOT_LOADED: "warn",
  NOT_TRAINED: "neutral",
  ERROR: "danger",
};

function statusNote(m: ModelInfo): string {
  if (m.status === "NOT_TRAINED") return "No trained artifact on disk yet.";
  if (m.status === "NOT_LOADED") return "Artifact present, not loaded into memory.";
  if (m.status === "ERROR") return m.error ?? "Manifest unreadable.";
  return "";
}

function ModelCard({ model, onLoad }: { model: ModelInfo; onLoad: (id: string) => void }) {
  return (
    <Card
      title={`${model.modality === "sign" ? "Sign recognition" : "Silent-lip recognition"}`}
      actions={<StatusBadge tone={statusTone[model.status]}>{model.status}</StatusBadge>}
    >
      <div className="space-y-2">
        <Row label="Model ID" value={model.model_id} />
        <Row label="Version" value={model.version} />
        <Row label="Preprocessing" value={model.preprocessing_version ?? "—"} />
        <Row label="Path" value={<span className="break-all">{model.path ?? "none"}</span>} />
        {model.evaluation ? (
          <Row
            label="Evaluation"
            value={
              <span>
                {Object.entries(model.evaluation).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}
              </span>
            }
          />
        ) : (
          <Row label="Evaluation" value="Unavailable — no training run yet" />
        )}
        {model.labels && model.labels.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {model.labels.map((l) => (
              <span key={l} className="data border border-line px-1.5 py-0.5 text-[11px]">
                {l}
              </span>
            ))}
          </div>
        )}
        <p className="text-[12px] text-ink-faint">{statusNote(model)}</p>
        <button
          type="button"
          onClick={() => onLoad(model.model_id)}
          className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper"
        >
          <Upload size={14} aria-hidden />
          Load model
        </button>
      </div>
    </Card>
  );
}

export default function AiLab() {
  const models = usePoll(() => api.models(), 15_000);
  const settings = usePoll(() => api.getSettings(), 30_000);
  const [loadMsg, setLoadMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function handleLoad(id: string) {
    setLoadMsg(null);
    try {
      await api.loadModel(id);
      setLoadMsg({ ok: true, text: `${id}: loaded` });
    } catch (err) {
      // Backend rejects honestly until the loader exists — surface its message verbatim.
      setLoadMsg({ ok: false, text: err instanceof ApiError ? err.message : "Unknown error" });
    }
    models.refresh();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">AI Lab</h1>
        {models.error && <StatusBadge tone="danger">{models.error}</StatusBadge>}
      </div>

      {loadMsg && (
        <div
          className={`border px-3 py-2 text-[13px] ${
            loadMsg.ok ? "border-ok/30 bg-ok-soft text-ok" : "border-warn/30 bg-warn-soft text-warn"
          }`}
          role="status"
        >
          {loadMsg.text}
        </div>
      )}

      {models.loading && !models.data ? (
        <LoadError error={models.error} loading />
      ) : models.data ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {models.data.models.map((m) => (
            <ModelCard key={m.modality} model={m} onLoad={handleLoad} />
          ))}
        </div>
      ) : (
        <LoadError error={models.error} loading={false} />
      )}

      <Card title="Fusion configuration (read-only here)">
        {settings.data ? (
          <div className="grid gap-x-8 md:grid-cols-2">
            <div>
              <Row label="Recognition mode" value={settings.data.recognition_mode} />
              <Row label="Sign threshold" value={settings.data.sign_threshold} />
              <Row label="Lip threshold" value={settings.data.lip_threshold} />
            </div>
            <div>
              <Row label="Min confidence" value={settings.data.min_confidence} />
              <Row
                label="Single-modality allowed"
                value={settings.data.allow_single_modality ? "yes" : "no"}
              />
              <Row label="Abstain label" value={settings.data.abstain_label} />
            </div>
          </div>
        ) : (
          <LoadError error={settings.error} loading={settings.loading} />
        )}
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-ink-faint">
          <Cpu size={13} aria-hidden />
          Thresholds are edited under Device Settings. Fusion rules are deterministic — see
          docs/architecture.md.
        </p>
      </Card>

      {!models.data?.models.some((m) => m.labels) && (
        <Empty text="No trained models exist yet — training arrives in Phases 5–6." />
      )}
    </div>
  );
}
