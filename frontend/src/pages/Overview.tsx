import { ArrowRight, Square, Play } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import { FramePreview } from "../components/vision/FramePreview";
import { fmt } from "../lib/utils";
import type { AppStatus, HistoryItem, ModelStatus, SystemMetrics } from "../types/api";

const modelTone = (s: ModelStatus) =>
  s === "LOADED" ? "ok" : s === "NOT_LOADED" ? "warn" : s === "ERROR" ? "danger" : "neutral";

const err = (e: unknown) => (e instanceof ApiError ? e.message : "Backend unreachable");

/** Thin real-value meter — no history implied, point-in-time only. */
function Meter({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-ink-soft">{label}</span>
        <span className="data text-[13px] font-medium text-ink">{fmt(value, unit)}</span>
      </div>
      {value !== null && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-line" aria-hidden>
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-500 ease-instrument"
            style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function RuntimePanel({
  s,
  onAction,
  busy,
}: {
  s: AppStatus | null;
  onAction: (start: boolean) => void;
  busy: boolean;
}) {
  const running = s?.runtime_state === "RUNNING";
  return (
    <Card
      title="Runtime"
      className="xl:col-span-7"
      actions={
        <div className="flex items-center gap-2">
          {s && (
            <StatusBadge tone={running ? "primary" : s.runtime_state === "ERROR" ? "danger" : "neutral"}>
              {s.runtime_state}
            </StatusBadge>
          )}
          {s &&
            (running ? (
              <button
                type="button"
                onClick={() => onAction(false)}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-sm border border-danger/40 bg-danger-soft px-2.5 py-1 text-[12px] text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
              >
                <Square size={12} aria-hidden /> Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onAction(true)}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-sm border border-primary/40 bg-primary-soft px-2.5 py-1 text-[12px] text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
              >
                <Play size={12} aria-hidden /> Start recognition
              </button>
            ))}
        </div>
      }
    >
      {s ? (
        <div className="space-y-1">
          <Row label="Recognition mode" value={s.recognition_mode} />
          <Row label="Camera" value={`${s.camera_provider} · ${s.camera_state}`} />
          <Row label="Sign model" value={<StatusBadge tone={modelTone(s.sign_model_status)}>{s.sign_model_status}</StatusBadge>} />
          <Row label="Lip model" value={<StatusBadge tone={modelTone(s.lip_model_status)}>{s.lip_model_status}</StatusBadge>} />
          <Row label="Speech" value={s.speech_enabled ? "enabled" : "disabled"} />
          <Row label="Inference latency" value={fmt(s.inference_latency_ms, " ms")} />
        </div>
      ) : (
        <LoadError error={null} loading />
      )}
    </Card>
  );
}

export default function Overview() {
  const status = usePoll(() => api.status(), 5_000);
  const metrics = usePoll(() => api.systemMetrics(), 5_000);
  const camera = usePoll(() => api.cameraStatus(), 3_000);
  const recent = usePoll(() => api.history(5, 0), 15_000);

  const s: AppStatus | null = status.data;
  const m: SystemMetrics | null = metrics.data;
  const camConnected = camera.data?.state === "CONNECTED";

  async function runtimeAction(start: boolean) {
    try {
      if (start) {
        await api.recognitionStart();
        toast.success("Recognition runtime started");
      } else {
        await api.recognitionStop();
        toast.success("Recognition runtime stopped");
      }
    } catch (e) {
      // Backend explains exactly why (e.g. models not trained yet) — surface verbatim.
      toast.error(err(e));
    }
    status.refresh();
  }

  const noEventHint = s
    ? s.runtime_state !== "RUNNING"
      ? `Runtime is ${s.runtime_state} — start it in the runtime panel.`
      : s.sign_model_status === "NOT_TRAINED" && s.lip_model_status === "NOT_TRAINED"
        ? "Both models are NOT_TRAINED — record a dataset and train in Training Center."
        : "Runtime is live — the first accepted decision will appear here."
    : "Status unavailable.";

  const items: HistoryItem[] = recent.data?.items ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        title="Communication console"
        description={
          s
            ? `${s.recognition_mode} mode · camera ${s.camera_state.toLowerCase()} · ${m?.hostname ?? "local host"}`
            : "Loading runtime status…"
        }
        status={status.error ? <StatusBadge tone="danger">{status.error}</StatusBadge> : undefined}
      />

      <div className="grid gap-4 xl:grid-cols-12">
        <RuntimePanel s={s} onAction={runtimeAction} busy={status.loading} />

        {/* Camera */}
        <Card
          title="Camera"
          className="xl:col-span-5"
          actions={
            <Link
              to="/vision"
              className="inline-flex items-center gap-1 text-[12px] text-primary transition-colors hover:text-primary-hover"
            >
              Live Vision <ArrowRight size={12} aria-hidden />
            </Link>
          }
        >
          <FramePreview
            active={camConnected}
            hint={
              <>
                Selected provider: <span className="data">{camera.data?.provider ?? "—"}</span>.
                Start it under Live Vision.
              </>
            }
          />
          <div className="mt-3">
            <Row label="Provider" value={camera.data?.provider ?? s?.camera_provider ?? "—"} />
            <Row
              label="Connection"
              value={
                <StatusBadge tone={camConnected ? "ok" : "neutral"}>
                  {camera.data?.state ?? "unavailable"}
                </StatusBadge>
              }
            />
            <Row
              label="Resolution · fps"
              value={
                camera.data?.width
                  ? `${camera.data.width}×${camera.data.height} · ${camera.data.fps ?? "—"} fps`
                  : "Unavailable"
              }
            />
          </div>
        </Card>

        {/* Latest recognition */}
        <Card title="Latest recognition" className="xl:col-span-4">
          {s?.last_message ? (
            <>
              <p className="display text-2xl leading-tight text-ink">{s.last_message}</p>
              <p className="mt-2 text-[12px] text-ink-faint">
                last accepted message from the fusion pipeline
              </p>
            </>
          ) : (
            <div className="space-y-1.5">
              <p className="display text-[19px] text-ink-faint">No recognition yet</p>
              <p className="text-[12px] leading-relaxed text-ink-faint">{noEventHint}</p>
            </div>
          )}
        </Card>

        {/* Model readiness */}
        <Card
          title="Model readiness"
          className="xl:col-span-4"
          actions={
            <Link to="/lab" className="text-[12px] text-primary transition-colors hover:text-primary-hover">
              AI Lab
            </Link>
          }
        >
          <Row
            label="Sign gesture"
            value={s ? <StatusBadge tone={modelTone(s.sign_model_status)}>{s.sign_model_status}</StatusBadge> : "—"}
          />
          <Row
            label="Silent lip"
            value={s ? <StatusBadge tone={modelTone(s.lip_model_status)}>{s.lip_model_status}</StatusBadge> : "—"}
          />
          <p className="mt-2 text-[12px] leading-relaxed text-ink-faint">
            Train models in{" "}
            <Link to="/training" className="text-ink-soft underline decoration-line-strong underline-offset-2 hover:text-ink">
              Training Center
            </Link>
            ; evaluate them in AI Lab.
          </p>
        </Card>

        {/* System health */}
        <Card title="System health" className="xl:col-span-4">
          {m ? (
            <div className="-my-1 divide-y divide-line/50">
              <Meter label="CPU" value={m.cpu_percent} unit="%" />
              <Meter label="Memory" value={m.memory_percent} unit="%" />
              <Meter label="Disk" value={m.disk_percent} unit="%" />
              <Meter label="Temperature" value={m.temperature_c} unit=" °C" />
            </div>
          ) : (
            <LoadError error={metrics.error} loading={metrics.loading} />
          )}
          <p className="mt-2 text-[11.5px] text-ink-faint">
            {m ? `${m.memory_used_mb} / ${m.memory_total_mb} MB · point-in-time, not a trend` : "No readings from this host."}
          </p>
        </Card>

        {/* Recent activity */}
        <Card
          title="Recent activity"
          className="xl:col-span-12"
          actions={
            <Link to="/history" className="inline-flex items-center gap-1 text-[12px] text-primary transition-colors hover:text-primary-hover">
              Full history <ArrowRight size={12} aria-hidden />
            </Link>
          }
        >
          {recent.loading && !recent.data ? (
            <LoadError error={recent.error} loading />
          ) : items.length === 0 ? (
            <Empty text="No stored decisions yet — every row here is a real database record once the runtime produces one." />
          ) : (
            <ul className="divide-y divide-line/50">
              {items.map((h) => (
                <li key={h.id} className="flex items-center gap-3 py-2 text-[13px]">
                  <span className="data w-36 shrink-0 text-[12px] text-ink-faint">
                    {new Date(h.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="data min-w-0 flex-1 truncate font-medium text-ink">{h.final_label}</span>
                  <span className="hidden text-ink-faint sm:inline">{h.reason}</span>
                  <StatusBadge tone={h.accepted ? "ok" : "warn"}>{h.accepted ? "accepted" : "rejected"}</StatusBadge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
