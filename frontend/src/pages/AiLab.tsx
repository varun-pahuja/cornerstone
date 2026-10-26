import { useState } from "react";
import { Cpu, FlaskConical, Hand, Smile, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, LoadError, MetricCell, Row } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { ModelInfo, ModelStatus } from "../types/api";

const statusTone: Record<ModelStatus, "ok" | "warn" | "danger" | "neutral"> = {
  LOADED: "ok",
  NOT_LOADED: "warn",
  NOT_TRAINED: "neutral",
  ERROR: "danger",
};

const err = (e: unknown) => (e instanceof ApiError ? e.message : "Backend unreachable");

function statusNote(m: ModelInfo): string {
  if (m.status === "NOT_TRAINED") return "No trained artifact on disk yet.";
  if (m.status === "NOT_LOADED") return "Artifact present, not loaded into memory.";
  if (m.status === "ERROR") return m.error ?? "Manifest unreadable.";
  return "Loaded into the recognition runtime.";
}

/** Confusion matrix only when the backend actually stored a 2D array. */
function Confusion({ matrix }: { matrix: number[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="data text-[11.5px]">
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={`border border-line px-2 py-1 text-right ${
                    i === j ? "bg-primary-soft text-primary" : "text-ink-soft"
                  }`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1.5 text-[11px] text-ink-faint">rows = true · cols = predicted</p>
    </div>
  );
}

function ModelPanel({ model, onLoad }: { model: ModelInfo; onLoad: (id: string) => void }) {
  const Icon = model.modality === "sign" ? Hand : Smile;
  const evalEntries = Object.entries(model.evaluation ?? {});
  const matrices = evalEntries.filter(
    (e): e is [string, number[][]] =>
      Array.isArray(e[1]) && e[1].length > 0 && e[1].every((r) => Array.isArray(r)),
  );
  const scalars = evalEntries.filter((e) => !matrices.some((m) => m[0] === e[0]));

  return (
    <Card
      title={model.modality === "sign" ? "Sign recognition" : "Silent-lip recognition"}
      actions={<StatusBadge tone={statusTone[model.status]}>{model.status}</StatusBadge>}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-sm border border-line bg-rail text-ink-soft">
          <Icon size={17} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <Row label="Model ID" value={model.model_id} />
          <Row label="Version" value={model.version} />
          <Row label="Preprocessing" value={model.preprocessing_version ?? "—"} />
          <Row
            label="Path"
            value={<span className="break-all">{model.path ?? "none"}</span>}
          />
        </div>
      </div>

      {scalars.length > 0 ? (
        <>
          <p className="label mt-4 mb-2">Evaluation</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {scalars.map(([k, v]) =>
              Array.isArray(v) && v.length === 0 ? null : (
                <MetricCell key={k} name={k} value={v} />
              ),
            )}
          </div>
        </>
      ) : (
        <p className="mt-4 text-[12.5px] text-ink-faint">
          Evaluation unavailable — no training run yet.
        </p>
      )}

      {matrices.length > 0 && (
        <div className="mt-4 space-y-3">
          {matrices.map(([k, v]) => (
            <div key={k}>
              <p className="label mb-1.5">{k.replace(/_/g, " ")}</p>
              <Confusion matrix={v} />
            </div>
          ))}
        </div>
      )}

      {model.labels && model.labels.length > 0 && (
        <div className="mt-4">
          <p className="label mb-1.5">Labels</p>
          <div className="flex flex-wrap gap-1.5">
            {model.labels.map((l) => (
              <span
                key={l}
                className="data rounded-sm border border-line bg-rail px-1.5 py-0.5 text-[11px] text-ink-soft"
              >
                {l}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-3">
        <p className="text-[12px] text-ink-faint">{statusNote(model)}</p>
        <button
          type="button"
          onClick={() => onLoad(model.model_id)}
          disabled={model.status !== "NOT_LOADED" && model.status !== "NOT_TRAINED"}
          className="inline-flex items-center gap-1.5 rounded-sm border border-line px-3 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-line-strong hover:text-ink disabled:opacity-40"
        >
          <Upload size={13} aria-hidden />
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
    try {
      await api.loadModel(id);
      toast.success(`${id}: loaded`);
      setLoadMsg({ ok: true, text: `${id}: loaded` });
    } catch (e) {
      // Backend rejects honestly until the loader exists — surface its message verbatim.
      const text = err(e);
      toast.error(text);
      setLoadMsg({ ok: false, text });
    }
    models.refresh();
  }

  const trained = models.data?.models.some((m) => m.labels) ?? false;

  return (
    <div className="space-y-5">
      <PageHeader
        title="AI Lab"
        description="Inspect trained artifacts, real evaluation metrics, and load models into the runtime."
        status={
          models.error ? <StatusBadge tone="danger">{models.error}</StatusBadge> : undefined
        }
      />

      {loadMsg && (
        <div
          className={`rounded-sm border px-3 py-2 text-[13px] ${
            loadMsg.ok
              ? "border-ok/30 bg-ok-soft text-ok"
              : "border-warn/30 bg-warn-soft text-warn"
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
            <ModelPanel key={m.modality} model={m} onLoad={handleLoad} />
          ))}
        </div>
      ) : (
        <LoadError error={models.error} loading={false} />
      )}

      {!trained && (
        <div className="rounded-md border border-dashed border-line-strong px-4 py-5">
          <p className="text-[13.5px] text-ink-soft">
            No trained models exist yet — nothing to evaluate.
          </p>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[12.5px] text-ink-faint">
            Record clips in{" "}
            <Link to="/dataset" className="text-primary underline underline-offset-2">
              Dataset Studio
            </Link>
            , then train in{" "}
            <Link to="/training" className="text-primary underline underline-offset-2">
              Training Center
            </Link>
            . Metrics only ever appear after a real run.
          </p>
        </div>
      )}

      <Card
        title="Fusion configuration"
        actions={
          <Link
            to="/settings"
            className="inline-flex items-center gap-1 text-[12px] text-primary transition-colors hover:text-primary-hover"
          >
            Edit in Device Settings
          </Link>
        }
      >
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
          Fusion rules are deterministic — see docs/architecture.md.{" "}
          <FlaskConical size={13} aria-hidden /> thresholds apply at the next runtime start.
        </p>
      </Card>
    </div>
  );
}
