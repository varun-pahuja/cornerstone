import { Terminal } from "lucide-react";
import { api } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, Row } from "../components/ui/Card";
import { fmt } from "../lib/utils";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";

export default function SystemHealth() {
  const metrics = usePoll(() => api.systemMetrics(), 5_000);
  const status = usePoll(() => api.status(), 5_000);
  const deps = usePoll(() => api.dependencies(), 60_000);
  const py = usePoll(() => api.pythonInfo(), 60_000);

  const m = metrics.data;
  const s = status.data;
  const d = deps.data;

  return (
    <div className="space-y-4">
      <PageHeader
        title="System Health"
        description="Point-in-time host metrics, runtime state, and dependency probes — read live, never synthesized."
        status={
          <>
            {metrics.error && <StatusBadge tone="danger">Metrics: {metrics.error}</StatusBadge>}
            {deps.error && <StatusBadge tone="danger">Deps: {deps.error}</StatusBadge>}
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="CPU">
          <p className="data text-[28px] font-medium">{fmt(m?.cpu_percent, "%")}</p>
        </Card>
        <Card title="Memory">
          <p className="data text-[28px] font-medium">{fmt(m?.memory_percent, "%")}</p>
          <p className="mt-1 text-[12px] text-ink-faint">
            {m ? `${m.memory_used_mb} / ${m.memory_total_mb} MB` : "Unavailable"}
          </p>
        </Card>
        <Card title="Disk">
          <p className="data text-[28px] font-medium">{fmt(m?.disk_percent, "%")}</p>
        </Card>
        <Card title="Temperature">
          <p className="data text-[28px] font-medium">
            {m?.temperature_c != null ? `${m.temperature_c} °C` : "Unavailable"}
          </p>
          <p className="mt-1 text-[12px] text-ink-faint">
            {m?.temperature_c == null ? "no sensor reading on this host" : "sensor reading"}
          </p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Runtime">
          {s ? (
            <>
              <Row label="State" value={<StatusBadge tone={s.runtime_state === "RUNNING" ? "ok" : "neutral"}>{s.runtime_state}</StatusBadge>} />
              <Row label="Camera" value={s.camera_state} />
              <Row label="Sign model" value={s.sign_model_status} />
              <Row label="Lip model" value={s.lip_model_status} />
              <Row label="Frames processed" value={s.last_recognition ? "see history" : "0"} />
              <Row label="Host" value={m?.hostname ?? "Unavailable"} />
              <Row label="Platform" value={m?.platform ?? "Unavailable"} />
            </>
          ) : (
            <LoadError error={status.error} loading={status.loading} />
          )}
        </Card>

        <Card title="Python">
          {py.data ? (
            <>
              <Row label="Version" value={<span className="break-all">{py.data.version.split(" ")[0]}</span>} />
              <Row label="Executable" value={<span className="break-all">{py.data.executable}</span>} />
              <Row label="Platform" value={py.data.platform} />
            </>
          ) : (
            <LoadError error={py.error} loading={py.loading} />
          )}
        </Card>
      </div>

      <Card
        title="Dependencies (probed at runtime)"
        actions={
          d && (
            <StatusBadge tone={d.offline_ok ? "ok" : "warn"}>
              {d.offline_ok ? "core offline OK" : "core missing"}
            </StatusBadge>
          )
        }
      >
        {d ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="label border-b border-line">
                    <th className="py-2 pr-3">Package</th>
                    <th className="py-2 pr-3">Kind</th>
                    <th className="py-2 pr-3">Available</th>
                    <th className="py-2 pr-3">Version</th>
                    <th className="py-2">Required for</th>
                  </tr>
                </thead>
                <tbody>
                  {d.dependencies.map((dep) => (
                    <tr key={dep.name} className="border-b border-line/50 last:border-0">
                      <td className="data py-2 pr-3 font-medium">{dep.name}</td>
                      <td className="py-2 pr-3 text-ink-soft">{dep.kind}</td>
                      <td className="py-2 pr-3">
                        <StatusBadge tone={dep.available ? "ok" : "warn"}>
                          {dep.available ? "yes" : "no"}
                        </StatusBadge>
                      </td>
                      <td className="data py-2 pr-3 text-ink-soft">{dep.version ?? "—"}</td>
                      <td className="py-2 text-ink-soft">{dep.required_for}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="mt-3 space-y-1">
              {d.notes.map((n) => (
                <li key={n} className="flex items-start gap-1.5 text-[12px] text-ink-faint">
                  <Terminal size={12} className="mt-0.5 shrink-0" aria-hidden />
                  {n}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <LoadError error={deps.error} loading={deps.loading} />
        )}
      </Card>

      {!d && <Empty text="Dependency probe not loaded yet." />}
    </div>
  );
}
