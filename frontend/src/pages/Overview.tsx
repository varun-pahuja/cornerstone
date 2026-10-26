import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../services/api";
import type { AppStatus, SystemMetrics } from "../types/api";
import { StatusBadge } from "../components/ui/StatusBadge";

type Load<T> = { data: T | null; error: string | null; loading: boolean };

function usePoll<T>(fetcher: () => Promise<T>, intervalMs: number): Load<T> & { refresh: () => void } {
  const [state, setState] = useState<Load<T>>({ data: null, error: null, loading: true });

  const load = useCallback(async () => {
    try {
      const data = await fetcher();
      setState({ data, error: null, loading: false });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Unknown error";
      setState((prev) => ({ data: prev.data, error: msg, loading: false }));
    }
  }, [fetcher]);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect
    load();
    const id = setInterval(load, intervalMs);
    return () => clearInterval(id);
  }, [load, intervalMs]);

  return { ...state, refresh: load };
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-line bg-panel">
      <h2 className="label border-b border-line px-4 py-2.5">{title}</h2>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 py-2 last:border-0">
      <span className="text-[13px] text-ink-soft">{label}</span>
      <span className="data text-[13px] font-medium">{value}</span>
    </div>
  );
}

const fmt = (v: number | null, unit: string): string =>
  v === null ? "Unavailable" : `${v}${unit}`;

export default function Overview() {
  const status = usePoll(() => api.status(), 5_000);
  const metrics = usePoll(() => api.systemMetrics(), 5_000);

  const s: AppStatus | null = status.data;
  const m: SystemMetrics | null = metrics.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
        <div className="flex gap-2">
          {status.error && <StatusBadge tone="danger">Status: {status.error}</StatusBadge>}
          {metrics.error && <StatusBadge tone="warn">Metrics: {metrics.error}</StatusBadge>}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Card title="Runtime">
          {s ? (
            <>
              <Row label="State" value={<StatusBadge tone={s.runtime_state === "RUNNING" ? "ok" : "neutral"}>{s.runtime_state}</StatusBadge>} />
              <Row label="Recognition mode" value={s.recognition_mode} />
              <Row label="Speech" value={s.speech_enabled ? "enabled" : "disabled"} />
            </>
          ) : (
            <p className="text-[13px] text-ink-faint">{status.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>

        <Card title="Camera">
          {s ? (
            <>
              <Row label="Provider" value={s.camera_provider} />
              <Row
                label="Connection"
                value={
                  <StatusBadge tone={s.camera_state === "CONNECTED" ? "ok" : "neutral"}>
                    {s.camera_state}
                  </StatusBadge>
                }
              />
            </>
          ) : (
            <p className="text-[13px] text-ink-faint">{status.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>

        <Card title="Models">
          {s ? (
            <>
              <Row label="Sign model" value={<StatusBadge tone="neutral">{s.sign_model_status}</StatusBadge>} />
              <Row label="Lip model" value={<StatusBadge tone="neutral">{s.lip_model_status}</StatusBadge>} />
            </>
          ) : (
            <p className="text-[13px] text-ink-faint">{status.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>

        <Card title="Last recognition">
          {s?.last_message ? (
            <p className="data text-lg font-semibold">{s.last_message}</p>
          ) : s ? (
            <p className="text-[13px] text-ink-faint">No recognition yet</p>
          ) : (
            <p className="text-[13px] text-ink-faint">{status.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>

        <Card title="System">
          {m ? (
            <>
              <Row label="CPU" value={fmt(m.cpu_percent, "%")} />
              <Row label="Memory" value={m.memory_percent !== null ? `${m.memory_percent}% (${m.memory_used_mb} / ${m.memory_total_mb} MB)` : "Unavailable"} />
              <Row label="Disk" value={fmt(m.disk_percent, "%")} />
              <Row label="Temperature" value={m.temperature_c !== null ? `${m.temperature_c} °C` : "Unavailable"} />
            </>
          ) : (
            <p className="text-[13px] text-ink-faint">{metrics.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>

        <Card title="Latency">
          {s ? (
            <>
              <Row label="Inference" value={s.inference_latency_ms !== null ? `${s.inference_latency_ms} ms` : "Unavailable"} />
              <Row label="Host" value={m?.hostname ?? "Unavailable"} />
            </>
          ) : (
            <p className="text-[13px] text-ink-faint">{status.loading ? "Loading…" : "Unavailable"}</p>
          )}
        </Card>
      </div>

      <p className="text-[13px] text-ink-faint">
        Start/stop controls appear here once the recognition runtime (Phase 3) is connected.
        No metric on this page is simulated.
      </p>
    </div>
  );
}
