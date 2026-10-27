import { useState } from "react";
import { FlaskConical, Hand, Smile, Square } from "lucide-react";
import { toast } from "sonner";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError, MetricCell } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { StatusBadge } from "../components/ui/StatusBadge";
import type { DatasetSummary, TrainingJobInfo } from "../types/api";

const err = (e: unknown) => (e instanceof ApiError ? e.message : "Backend unreachable");

const statusTone = (s: string) =>
  s === "COMPLETED"
    ? "ok"
    : s === "FAILED" || s === "CANCELLED"
      ? "danger"
      : s === "RUNNING"
        ? "info"
        : "neutral";

type CurvePoint = { epoch: number; loss: number | null; accuracy: number | null };

/**
 * Parses ONLY what the backend actually logged — log rows are `{ts, line}` records;
 * accepts their "epoch 3/40 loss=1.2345 acc=0.4500" lines or structured
 * `{epoch, loss, accuracy}` objects. Zero matches → empty chart state.
 */
function parseCurve(logs: unknown[]): CurvePoint[] {
  const pts: CurvePoint[] = [];
  for (const raw of logs) {
    const entry =
      raw && typeof raw === "object" && !Array.isArray(raw) && "line" in raw
        ? (raw as { line?: unknown }).line
        : raw;
    if (entry && typeof entry === "object" && !Array.isArray(entry)) {
      const o = entry as Record<string, unknown>;
      if (typeof o.epoch === "number") {
        pts.push({
          epoch: o.epoch,
          loss: typeof o.loss === "number" ? o.loss : null,
          accuracy:
            typeof o.accuracy === "number"
              ? o.accuracy
              : typeof o.acc === "number"
                ? o.acc
                : null,
        });
        continue;
      }
    }
    if (typeof entry === "string") {
      // worker logs "epoch 3/40 loss=1.2345" (accuracy only when a run logs it)
      const m = /epoch\s+(\d+)\/(\d+)\s+loss=([\d.]+)(?:\s+acc(?:uracy)?=([\d.]+))?/.exec(entry);
      if (m) {
        pts.push({
          epoch: Number(m[1]),
          loss: Number(m[3]),
          accuracy: m[4] !== undefined ? Number(m[4]) : null,
        });
      }
    }
  }
  return pts;
}

/** Extract displayable text lines from `{ts, line}` records (or raw strings). */
function logText(logs: unknown[]): string[] {
  return logs.flatMap((l) => {
    if (typeof l === "string") return [l];
    if (l && typeof l === "object" && !Array.isArray(l) && "line" in l) {
      const line = (l as { line?: unknown }).line;
      if (typeof line === "string") {
        const ts = (l as { ts?: unknown }).ts;
        return [typeof ts === "string" ? `${ts}  ${line}` : line];
      }
    }
    return [];
  });
}

/** metrics may nest (e.g. evaluation.accuracy) — flatten one level for cells. */
function flattenMetrics(m: Record<string, unknown>): [string, unknown][] {
  const out: [string, unknown][] = [];
  for (const [k, v] of Object.entries(m)) {
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      for (const [k2, v2] of Object.entries(v)) out.push([`${k}.${k2}`, v2]);
    } else {
      out.push([k, v]);
    }
  }
  return out;
}

function EpochStepper({ job }: { job: TrainingJobInfo }) {
  const total = job.total_epochs;
  if (total <= 0) {
    return <p className="text-[12.5px] text-ink-faint">Not started yet.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <span className="data text-[13px] font-medium text-ink">
          epoch {job.current_epoch}/{total}
        </span>
        <span className="data text-[12px] text-ink-faint">
          {Math.round(job.progress * 100)}%
        </span>
        {job.status === "RUNNING" && (
          <span className="label flex items-center gap-1.5 text-primary">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" aria-hidden />
            training
          </span>
        )}
      </div>
      {/* one tick per epoch — real progress, capped render for long runs */}
      <div className="flex flex-wrap gap-[3px]" aria-hidden>
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className={`h-1.5 w-3 rounded-[1px] ${
              i < job.current_epoch ? "bg-primary" : "bg-line"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

function JobDetail({ jobId }: { jobId: number }) {
  const detail = usePoll(() => api.trainingJob(jobId), 3_000);
  const job = detail.data?.job;
  const logs = detail.data?.logs ?? [];
  const curve = parseCurve(logs);
  const textLogs = logText(logs);
  const metrics = job?.metrics ? flattenMetrics(job.metrics) : [];
  const mappable = metrics.filter(
    ([, v]) => typeof v === "number" || typeof v === "string" || typeof v === "boolean" || v === null,
  );

  if (detail.loading && !detail.data) return <LoadError error={detail.error} loading />;
  if (!job) return <LoadError error={detail.error} loading={false} />;

  return (
    <Card
      title={`Job #${job.id} · ${job.modality} · ${job.dataset}`}
      actions={<StatusBadge tone={statusTone(job.status)}>{job.status}</StatusBadge>}
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          <EpochStepper job={job} />

          {job.error && (
            <div className="rounded-sm border border-danger/30 bg-danger-soft px-3 py-2 text-[12.5px] text-danger">
              {job.error}
            </div>
          )}

          {mappable.length > 0 && (
            <div>
              <p className="label mb-2">Recorded metrics (real, from this run)</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {mappable.map(([k, v]) => (
                  <MetricCell key={k} name={k} value={v} />
                ))}
              </div>
            </div>
          )}

          {/* Real loss/accuracy curve — only if the backend logged epoch lines */}
          <div>
            <p className="label mb-2">Training curve</p>
            {curve.length >= 2 ? (
              <div className="h-[220px] w-full rounded-sm border border-line bg-rail p-2">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={curve} margin={{ top: 6, right: 6, bottom: 0, left: -14 }}>
                    <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="epoch"
                      tick={{ fill: "var(--color-ink-faint)", fontSize: 11 }}
                      axisLine={{ stroke: "var(--color-line-strong)" }}
                      tickLine={false}
                    />
                    <YAxis
                      yAxisId="loss"
                      tick={{ fill: "var(--color-ink-faint)", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={46}
                    />
                    <YAxis
                      yAxisId="acc"
                      orientation="right"
                      domain={[0, 1]}
                      tick={{ fill: "var(--color-ink-faint)", fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                      width={34}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "var(--color-elevated)",
                        border: "1px solid var(--color-line)",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "var(--color-ink)" }}
                    />
                    <Line
                      yAxisId="loss"
                      type="monotone"
                      dataKey="loss"
                      stroke="var(--color-primary)"
                      strokeWidth={1.75}
                      dot={false}
                    />
                    <Line
                      yAxisId="acc"
                      type="monotone"
                      dataKey="accuracy"
                      stroke="var(--color-info)"
                      strokeWidth={1.75}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-[12.5px] text-ink-faint">
                No curve data — the backend logs one line per epoch while a job runs.
              </p>
            )}
          </div>
        </div>

        <div>
          <p className="label mb-2">Log tail</p>
          {textLogs.length > 0 ? (
            <pre className="data max-h-[420px] overflow-y-auto rounded-sm border border-line bg-rail p-3 text-[11.5px] leading-relaxed whitespace-pre-wrap text-ink-soft">
              {textLogs.slice(-40).join("\n")}
            </pre>
          ) : (
            <p className="text-[12.5px] text-ink-faint">
              No log lines stored for this job yet.
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function TrainingCenter() {
  const jobs = usePoll(() => api.trainingJobs(), 5_000);
  const datasets = usePoll(() => api.datasets(), 15_000);
  const [selected, setSelected] = useState<number | null>(null);
  const [modality, setModality] = useState<"sign" | "lip">("sign");
  const [datasetId, setDatasetId] = useState<string>("");
  const [creating, setCreating] = useState(false);

  const list: TrainingJobInfo[] = jobs.data ?? [];
  const dsets: DatasetSummary[] = datasets.data ?? [];

  // derived, not effect-driven: first real dataset until the user picks one
  const effectiveDataset = datasetId || dsets[0]?.dataset_id || "";
  // close the detail pane only when the list is real and no longer contains it
  const detailId =
    selected !== null && (list.length === 0 || list.some((j) => j.id === selected))
      ? selected
      : null;

  const active = list.find((j) => j.status === "RUNNING" || j.status === "QUEUED");

  async function handleCreate() {
    setCreating(true);
    try {
      const res = await api.createTrainingJob({
        modality,
        dataset: effectiveDataset || "default",
      });
      toast.success(`Job #${res.job?.id ?? ""} queued`);
      jobs.refresh();
    } catch (e) {
      // Backend precheck explains why (e.g. too few clips) — surface verbatim.
      toast.error(err(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleCancel(id: number) {
    try {
      await api.cancelTrainingJob(id);
      toast.success(`Job #${id} cancelled`);
      jobs.refresh();
    } catch (e) {
      toast.error(err(e));
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Training Center"
        description="Queue sign-model training on recorded datasets. Progress and curves come from the real run — nothing is simulated."
        status={
          jobs.error ? (
            <StatusBadge tone="danger">{jobs.error}</StatusBadge>
          ) : active ? (
            <StatusBadge tone={active.status === "RUNNING" ? "info" : "neutral"}>
              job #{active.id} {active.status.toLowerCase()}
            </StatusBadge>
          ) : undefined
        }
      />

      <div className="grid gap-4 xl:grid-cols-12">
        {/* Job list */}
        <Card
          title="Jobs"
          className="xl:col-span-7"
          actions={
            <span className="label">{list.length} total</span>
          }
        >
          {jobs.loading && !jobs.data ? (
            <LoadError error={jobs.error} loading />
          ) : list.length === 0 ? (
            <div className="space-y-2">
              <Empty text="No training jobs yet." />
              <p className="text-[12px] leading-relaxed text-ink-faint">
                The pipeline is validation → baseline train → evaluation → export (runs
                in-process; see docs/architecture.md). Creating a job with too few clips is
                rejected before any row is written — no fake jobs are ever queued.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-line/50">
              {list.map((j) => (
                <li key={j.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(j.id)}
                    className={`flex w-full items-center gap-3 px-1 py-2.5 text-left transition-colors ${
                      selected === j.id ? "bg-rail-hover" : "hover:bg-rail-hover/60"
                    }`}
                  >
                    <span className="data w-10 shrink-0 text-[12px] text-ink-faint">#{j.id}</span>
                    <span className="flex min-w-0 flex-1 items-center gap-2">
                      <Hand size={13} className="shrink-0 text-ink-faint" aria-hidden />
                      <span className="truncate text-[13px] text-ink">{j.dataset}</span>
                    </span>
                    <span className="hidden w-40 shrink-0 sm:block">
                      {j.total_epochs > 0 ? (
                        <span className="block h-1 w-full overflow-hidden rounded-full bg-line">
                          <span
                            className="block h-full rounded-full bg-primary transition-[width] duration-500 ease-instrument"
                            style={{ width: `${Math.round(j.progress * 100)}%` }}
                          />
                        </span>
                      ) : (
                        <span className="text-[11.5px] text-ink-faint">not started</span>
                      )}
                    </span>
                    <StatusBadge tone={statusTone(j.status)}>{j.status}</StatusBadge>
                    {(j.status === "QUEUED" || j.status === "RUNNING") && (
                      <span
                        role="button"
                        tabIndex={0}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancel(j.id);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            handleCancel(j.id);
                          }
                        }}
                        className="inline-flex shrink-0 items-center gap-1 rounded-sm border border-line px-2 py-1 text-[11.5px] text-ink-soft transition-colors hover:border-danger/40 hover:text-danger"
                      >
                        <Square size={10} aria-hidden /> Cancel
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* New job */}
        <Card title="New training job" className="xl:col-span-5">
          <fieldset className="space-y-4">
            <div>
              <legend className="label mb-2">Modality</legend>
              <div className="flex gap-2">
                <label
                  className={`flex flex-1 cursor-pointer items-center gap-2 rounded-sm border px-3 py-2.5 text-[13px] transition-colors ${
                    modality === "sign"
                      ? "border-primary/50 bg-primary-soft text-primary"
                      : "border-line text-ink-soft hover:border-line-strong"
                  }`}
                >
                  <input
                    type="radio"
                    name="modality"
                    value="sign"
                    checked={modality === "sign"}
                    onChange={() => setModality("sign")}
                    className="sr-only"
                  />
                  <Hand size={15} aria-hidden /> Sign gestures
                </label>
                <label
                  title="Silent-lip training arrives in Phase 6"
                  className="flex flex-1 cursor-not-allowed items-center gap-2 rounded-sm border border-line px-3 py-2.5 text-[13px] text-ink-faint opacity-60"
                >
                  <input type="radio" name="modality" value="lip" disabled className="sr-only" />
                  <Smile size={15} aria-hidden /> Silent-lip (Phase 6)
                </label>
              </div>
            </div>

            <div>
              <label htmlFor="dataset" className="label mb-2 block">
                Dataset
              </label>
              {dsets.length === 0 ? (
                <p className="text-[13px] text-ink-faint">
                  No datasets found — record clips in Dataset Studio first.
                </p>
              ) : (
                <select
                  id="dataset"
                  value={effectiveDataset}
                  onChange={(e) => setDatasetId(e.target.value)}
                  className="w-full rounded-sm border border-line bg-rail px-3 py-2.5 text-[13px] text-ink outline-none focus-visible:border-primary/60"
                >
                  {dsets.map((d) => (
                    <option key={d.dataset_id} value={d.dataset_id}>
                      {d.name} ({d.clip_count} clips)
                    </option>
                  ))}
                </select>
              )}
              <p className="mt-2 text-[11.5px] leading-relaxed text-ink-faint">
                A dataset needs ≥ 4 sign clips across ≥ 2 classes after a participant-safe
                split, or the backend refuses before creating a job.
              </p>
            </div>

            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || dsets.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-sm border border-primary/50 bg-primary-soft px-4 py-2.5 text-[14px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
            >
              <FlaskConical size={15} aria-hidden />
              {creating ? "Submitting…" : "Start training"}
            </button>
          </fieldset>
        </Card>
      </div>

      {detailId !== null && <JobDetail jobId={detailId} />}
    </div>
  );
}
