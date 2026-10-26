import { useState } from "react";
import { Camera, CameraOff, Plug, Square, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import { FramePreview } from "../components/vision/FramePreview";
import type { HistoryItem, ModelStatus, RecognitionStatus } from "../types/api";

const err = (e: unknown) => (e instanceof ApiError ? e.message : "Backend unreachable");

const modelTone = (s: ModelStatus) =>
  s === "LOADED" ? "ok" : s === "NOT_LOADED" ? "warn" : s === "ERROR" ? "danger" : "neutral";

/** Defensive renderer for last_decision — real object, unknown schema, no fabrication. */
function DecisionFields({ decision }: { decision: Record<string, unknown> }) {
  const entries = Object.entries(decision).slice(0, 10);
  return (
    <dl className="divide-y divide-line/50">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-baseline justify-between gap-3 py-1.5">
          <dt className="text-[12px] text-ink-soft">{k}</dt>
          <dd className="data max-w-[60%] truncate text-right text-[12px] font-medium text-ink">
            {v === null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function LiveVision() {
  const cameras = usePoll(() => api.cameras(), 15_000);
  const camStatus = usePoll(() => api.cameraStatus(), 2_000);
  const caps = usePoll(() => api.cameraCapabilities(), 60_000);
  const recog = usePoll(() => api.recognitionStatus(), 5_000);
  const timeline = usePoll(() => api.history(8, 0), 10_000);
  const [busy, setBusy] = useState(false);

  const st = camStatus.data;
  const connected = st?.state === "CONNECTED";
  const r: RecognitionStatus | null = recog.data;

  async function handleStart() {
    setBusy(true);
    try {
      await api.cameraStart();
      toast.success("Camera started");
    } catch (e) {
      toast.error(err(e));
    } finally {
      setBusy(false);
      camStatus.refresh();
    }
  }

  async function handleStop() {
    setBusy(true);
    try {
      await api.cameraStop();
      toast.success("Camera stopped");
    } catch (e) {
      toast.error(err(e));
    } finally {
      setBusy(false);
      camStatus.refresh();
    }
  }

  const items: HistoryItem[] = timeline.data?.items ?? [];
  const provider = st?.provider ?? "unknown provider";

  return (
    <div className="space-y-5">
      <PageHeader
        title="Live Vision"
        description={
          connected
            ? `Receiving frames from ${provider}${st?.width ? ` · ${st.width}×${st.height}` : ""}`
            : `Vision workstation · provider ${provider} not producing frames`
        }
        status={
          st && (
            <StatusBadge
              tone={connected ? "ok" : st.state === "ERROR" || st.state === "UNAVAILABLE" ? "danger" : "neutral"}
            >
              {st.state}
            </StatusBadge>
          )
        }
        actions={
          connected ? (
            <button
              type="button"
              onClick={handleStop}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-sm border border-danger/40 bg-danger-soft px-3 py-1.5 text-[13px] text-danger transition-colors hover:bg-danger/20 disabled:opacity-50"
            >
              <Square size={14} aria-hidden /> Stop camera
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStart}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-sm border border-primary/50 bg-primary-soft px-3 py-1.5 text-[13px] text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
            >
              <Camera size={14} aria-hidden />
              {busy ? "Starting…" : "Start camera"}
            </button>
          )
        }
      />

      <div className="grid gap-4 xl:grid-cols-12">
        {/* ---- Main workstation ---- */}
        <div className="space-y-4 xl:col-span-9">
          <Card
            title="Preview"
            actions={
              <span className="data text-[11px] text-ink-faint">
                {st ? `${st.frames_captured} captured · ${st.frames_dropped} stale dropped` : ""}
              </span>
            }
          >
            <div className="relative">
              <FramePreview
                active={connected}
                badge={
                  st?.width ? (
                    <span className="data rounded-sm border border-line bg-panel/85 px-2 py-1 text-[10.5px] text-ink-soft">
                      {st.width}×{st.height} · {st.fps ?? "—"} fps
                    </span>
                  ) : undefined
                }
                hint={
                  <>
                    Provider <span className="data">{provider}</span> is{" "}
                    <span className="data">{st?.state ?? "unavailable"}</span>. Connect a USB camera,
                    or switch provider under{" "}
                    <Link to="/settings" className="text-primary underline underline-offset-2">
                      Device Settings
                    </Link>
                    . No placeholder video is ever shown.
                  </>
                }
              />
              {/* Framing guidance — chrome only, never a fake detection overlay */}
              {connected && (
                <div className="pointer-events-none absolute inset-0" aria-hidden>
                  <div className="absolute inset-6 rounded-sm border border-white/10" />
                  <div className="absolute bottom-10 left-1/2 -translate-x-1/2 rounded-sm bg-black/50 px-2.5 py-1 font-mono text-[10.5px] tracking-[0.06em] text-white/70 uppercase">
                    keep hands / face inside frame
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Recognition lanes — honest states only */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card
              title="Sign recognition"
              actions={
                r && <StatusBadge tone={modelTone(r.sign_model)}>{r.sign_model}</StatusBadge>
              }
            >
              <p className="text-[13px] text-ink-soft">
                {r?.sign_model === "LOADED"
                  ? "Model loaded — gestures classified per frame."
                  : r
                    ? "Model not loaded. Train a sign model in Training Center."
                    : "Recognition status unavailable."}
              </p>
            </Card>
            <Card
              title="Silent-lip recognition"
              actions={r && <StatusBadge tone={modelTone(r.lip_model)}>{r.lip_model}</StatusBadge>}
            >
              <p className="text-[13px] text-ink-soft">
                {r?.lip_model === "LOADED"
                  ? "Model loaded — mouth-region frames classified per window."
                  : r
                    ? "Model not trained yet (Phase 6). This lane stays honest until it exists."
                    : "Recognition status unavailable."}
              </p>
            </Card>
            <Card
              title="Fusion result"
              actions={r && <StatusBadge tone={r.runtime_state === "RUNNING" ? "primary" : "neutral"}>{r.runtime_state}</StatusBadge>}
            >
              {r?.last_decision ? (
                <DecisionFields decision={r.last_decision} />
              ) : (
                <p className="text-[13px] text-ink-faint">
                  No fused decision yet. Confidence appears here only when a model produces one.
                </p>
              )}
            </Card>
          </div>

          {/* Event timeline */}
          <Card
            title="Recognition events"
            actions={
              <Link to="/history" className="text-[12px] text-primary hover:text-primary-hover">
                Full history
              </Link>
            }
          >
            {timeline.loading && !timeline.data ? (
              <LoadError error={timeline.error} loading />
            ) : items.length === 0 ? (
              <Empty text="No events yet — decisions appear here as the runtime stores them." />
            ) : (
              <ol className="relative space-y-0 border-l border-line pl-4">
                {items.map((h) => (
                  <li key={h.id} className="relative py-2.5">
                    <span
                      className={`absolute -left-[21px] top-4 h-2 w-2 rounded-full ${
                        h.accepted ? "bg-ok" : "bg-warn"
                      }`}
                      aria-hidden
                    />
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="data text-[11.5px] text-ink-faint">
                        {new Date(h.timestamp).toLocaleTimeString()}
                      </span>
                      <span className="data text-[13px] font-medium text-ink">{h.final_label}</span>
                      <StatusBadge tone={h.accepted ? "ok" : "warn"}>
                        {h.accepted ? "accepted" : "abstained"}
                      </StatusBadge>
                      <span className="text-[12px] text-ink-faint">{h.reason}</span>
                      {h.latency_ms !== null && (
                        <span className="data text-[11.5px] text-ink-faint">{h.latency_ms} ms</span>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>

        {/* ---- Side rail ---- */}
        <div className="space-y-4 xl:col-span-3">
          <Card title="Camera status">
            {st ? (
              <>
                <Row label="State" value={st.state} />
                <Row label="Provider" value={st.provider} />
                <Row label="Resolution" value={st.width ? `${st.width}×${st.height}` : "Unavailable"} />
                <Row label="FPS" value={st.fps ?? "Unavailable"} />
                <Row label="Frames captured" value={st.frames_captured} />
                <Row label="Stale dropped" value={st.frames_dropped} />
                <Row
                  label="Last frame age"
                  value={st.last_frame_age_ms !== null ? `${st.last_frame_age_ms} ms` : "Unavailable"}
                />
                {st.error && <Row label="Error" value={<span className="text-danger">{st.error}</span>} />}
              </>
            ) : (
              <LoadError error={camStatus.error} loading={camStatus.loading} />
            )}
          </Card>

          <Card title="Sources">
            {cameras.loading && !cameras.data ? (
              <LoadError error={cameras.error} loading />
            ) : (
              <ul className="space-y-2">
                {(cameras.data ?? []).map((c) => (
                  <li key={c.provider} className="flex items-start justify-between gap-2 text-[12px]">
                    <span className="text-ink-soft">
                      {c.label}
                      {c.device_path && <span className="data block text-ink-faint">{c.device_path}</span>}
                      {c.detail && <span className="block text-ink-faint">{c.detail}</span>}
                    </span>
                    <StatusBadge tone={c.available ? "ok" : "neutral"}>
                      {c.available ? "available" : "unavailable"}
                    </StatusBadge>
                  </li>
                ))}
              </ul>
            )}
            {!connected && (
              <p className="mt-3 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-ink-faint">
                <CameraOff size={13} className="mt-0.5 shrink-0" aria-hidden />
                <span>
                  Selected provider: <span className="data">{provider}</span>. Provider changes are
                  made under Device Settings and need a backend restart.
                </span>
              </p>
            )}
          </Card>

          <Card
            title="Kernel capabilities"
            actions={<span className="label">V4L2</span>}
          >
            {caps.data ? (
              caps.data.v4l2_devices.length > 0 ? (
                <ul className="space-y-1.5">
                  {caps.data.v4l2_devices.map((d) => (
                    <li key={d.device_path} className="flex items-center gap-2 text-[12.5px]">
                      <Plug size={13} className="shrink-0 text-ink-faint" aria-hidden />
                      <span className="data">{d.device_path}</span>
                      <span className="truncate text-ink-soft">{d.name}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty text="No V4L2 video devices detected on this machine." />
              )
            ) : (
              <LoadError error={caps.error} loading={caps.loading} />
            )}
            {caps.data && <p className="mt-2 text-[11.5px] text-ink-faint">{caps.data.note}</p>}
          </Card>

          <Card title="Next step">
            <p className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-soft">
              <Wand2 size={14} className="mt-0.5 shrink-0 text-primary" aria-hidden />
              {st?.state === "DISCONNECTED" || !st
                ? "Start the camera to feed the preview, dataset recording, and recognition runtime."
                : "Camera is live — start the recognition runtime from the Overview once models are trained."}
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
