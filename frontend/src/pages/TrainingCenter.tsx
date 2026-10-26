import { useState } from "react";
import { FlaskConical, Square } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { TrainingJobInfo } from "../types/api";

const statusTone = (s: string) =>
  s === "COMPLETED" ? "ok" : s === "FAILED" || s === "CANCELLED" ? "danger" : s === "RUNNING" ? "info" : "neutral";

export default function TrainingCenter() {
  const jobs = usePoll(() => api.trainingJobs(), 10_000);
  const [msg, setMsg] = useState<string | null>(null);

  async function handleCreate() {
    setMsg(null);
    try {
      // Backend rejects job creation until Phase 5 — show its reason verbatim.
      await api.createTrainingJob({ modality: "sign", dataset: "default" });
      jobs.refresh();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    }
  }

  async function handleCancel(id: number) {
    setMsg(null);
    try {
      await api.cancelTrainingJob(id);
      jobs.refresh();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Training Center</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleCreate}
            className="inline-flex items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] hover:bg-paper"
          >
            <FlaskConical size={14} aria-hidden />
            New training job
          </button>
        </div>
      </div>

      {msg && (
        <div className="border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-warn" role="status">
          {msg}
        </div>
      )}

      <Card title="Jobs">
        {jobs.loading && !jobs.data ? (
          <LoadError error={jobs.error} loading />
        ) : jobs.data && jobs.data.length > 0 ? (
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="label border-b border-line">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Modality</th>
                <th className="py-2 pr-3">Dataset</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Progress</th>
                <th className="py-2 pr-3">Created</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {jobs.data.map((j: TrainingJobInfo) => (
                <tr key={j.id} className="border-b border-line/50 last:border-0">
                  <td className="data py-2 pr-3">{j.id}</td>
                  <td className="py-2 pr-3">{j.modality}</td>
                  <td className="py-2 pr-3">{j.dataset}</td>
                  <td className="py-2 pr-3">
                    <StatusBadge tone={statusTone(j.status)}>{j.status}</StatusBadge>
                  </td>
                  <td className="data py-2 pr-3">
                    {j.total_epochs > 0 ? `${j.current_epoch}/${j.total_epochs}` : "—"}
                    {j.error && <span className="ml-2 text-danger">{j.error}</span>}
                  </td>
                  <td className="data py-2 pr-3 text-ink-soft">
                    {new Date(j.created_at).toLocaleString()}
                  </td>
                  <td className="py-2 text-right">
                    {(j.status === "QUEUED" || j.status === "RUNNING") && (
                      <button
                        type="button"
                        onClick={() => handleCancel(j.id)}
                        className="inline-flex items-center gap-1 border border-line px-2 py-1 text-[12px] hover:bg-paper"
                      >
                        <Square size={11} aria-hidden /> Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="space-y-2">
            <Empty text="No training jobs yet." />
            <p className="text-[12px] text-ink-faint">
              The training pipeline (data validation → baseline train → evaluation → export)
              arrives in Phases 5–6. Creating a job now is rejected by the backend with a reason —
              no fake jobs are ever queued.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
