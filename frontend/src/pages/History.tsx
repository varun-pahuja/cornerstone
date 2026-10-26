import { useState } from "react";
import { Trash2 } from "lucide-react";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { HistoryItem } from "../types/api";

const PAGE = 25;

function cell(v: string | number | null | undefined, fallback = "—"): string {
  return v === null || v === undefined || v === "" ? fallback : String(v);
}

export default function History() {
  const [offset, setOffset] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const history = usePoll(() => api.history(PAGE, offset), 10_000, [offset]);

  async function handleClear() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    setMsg(null);
    try {
      const res = await api.clearHistory();
      setMsg(`Cleared ${res.cleared} entries`);
      setOffset(0);
      history.refresh();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Backend unreachable");
    }
  }

  const total = history.data?.total ?? 0;
  const items: HistoryItem[] = history.data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Recognition History"
        description="Every stored fusion decision — a real database record, nothing prefilled."
        status={total > 0 ? <StatusBadge tone="neutral">{total} rows</StatusBadge> : undefined}
        actions={
          <button
            type="button"
            onClick={handleClear}
            disabled={total === 0}
            className={`inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-[13px] transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              confirming
                ? "border-danger/50 bg-danger-soft text-danger"
                : "border-line text-ink-soft hover:border-line-strong hover:text-ink"
            }`}
          >
            <Trash2 size={14} aria-hidden />
            {confirming ? "Click again to confirm" : "Clear history"}
          </button>
        }
      />

      {msg && (
        <div
          className="rounded-sm border border-line bg-elevated px-3 py-2 text-[13px] text-ink-soft"
          role="status"
        >
          {msg}
        </div>
      )}

      <Card title={`Stored decisions (${total})`}>
        {history.loading && !history.data ? (
          <LoadError error={history.error} loading />
        ) : items.length === 0 ? (
          <div className="space-y-2">
            <Empty text="No recognition decisions yet." />
            <p className="text-[12px] text-ink-faint">
              Entries appear once the recognition runtime produces decisions. Every row here is a
              real database record — nothing is prefilled.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="label border-b border-line">
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Mode</th>
                  <th className="py-2 pr-3">Sign</th>
                  <th className="py-2 pr-3">Lip</th>
                  <th className="py-2 pr-3">Final</th>
                  <th className="py-2 pr-3">Accepted</th>
                  <th className="py-2 pr-3">Reason</th>
                  <th className="py-2">Latency</th>
                </tr>
              </thead>
              <tbody>
                {items.map((h) => (
                  <tr key={h.id} className="border-b border-line/50 last:border-0">
                    <td className="data py-2 pr-3 whitespace-nowrap text-ink-soft">
                      {new Date(h.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 pr-3">{h.mode}</td>
                    <td className="data py-2 pr-3">
                      {cell(h.sign_label)}
                      {h.sign_confidence !== null && (
                        <span className="text-ink-faint"> ({h.sign_confidence.toFixed(2)})</span>
                      )}
                    </td>
                    <td className="data py-2 pr-3">
                      {cell(h.lip_label)}
                      {h.lip_confidence !== null && (
                        <span className="text-ink-faint"> ({h.lip_confidence.toFixed(2)})</span>
                      )}
                    </td>
                    <td className="data py-2 pr-3 font-medium">{h.final_label}</td>
                    <td className="py-2 pr-3">
                      <StatusBadge tone={h.accepted ? "ok" : "warn"}>
                        {h.accepted ? "yes" : "no"}
                      </StatusBadge>
                    </td>
                    <td className="py-2 pr-3 text-ink-soft">{h.reason}</td>
                    <td className="data py-2 text-ink-soft">
                      {h.latency_ms !== null ? `${h.latency_ms} ms` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setOffset((o) => Math.max(0, o - PAGE))}
                disabled={offset === 0}
                className="rounded-sm border border-line px-3 py-1 text-[13px] text-ink-soft transition-colors hover:border-line-strong hover:text-ink disabled:opacity-40"
              >
                Previous
              </button>
              <span className="data text-[12px] text-ink-faint">
                {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
              </span>
              <button
                type="button"
                onClick={() => setOffset((o) => o + PAGE)}
                disabled={offset + PAGE >= total}
                className="rounded-sm border border-line px-3 py-1 text-[13px] text-ink-soft transition-colors hover:border-line-strong hover:text-ink disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
