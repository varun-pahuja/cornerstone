import { Database, FileVideo, PackageOpen } from "lucide-react";
import { api } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, Empty, LoadError } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";

export default function DatasetStudio() {
  const stats = usePoll(() => api.datasetStats(), 15_000);
  const datasets = usePoll(() => api.datasets(), 15_000);

  const s = stats.data;
  const classes = s ? Object.entries(s.by_class) : [];
  const modalities = s ? Object.entries(s.by_modality) : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Dataset Studio</h1>
        <button
          type="button"
          disabled
          title="Import API arrives in Phase 4 — this button does nothing yet, by design"
          className="inline-flex cursor-not-allowed items-center gap-1.5 border border-line px-3 py-1.5 text-[13px] text-ink-faint opacity-60"
        >
          <PackageOpen size={14} aria-hidden />
          Import clips — Phase 4
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Clips">
          {s ? (
            <p className="data text-3xl font-semibold">{s.total_clips}</p>
          ) : (
            <LoadError error={stats.error} loading={stats.loading} />
          )}
          <p className="mt-1 text-[12px] text-ink-faint">counted from manifests on disk</p>
        </Card>
        <Card title="Raw video files">
          {s ? (
            <p className="data text-3xl font-semibold">{s.raw_video_files}</p>
          ) : (
            <LoadError error={stats.error} loading={stats.loading} />
          )}
          <p className="mt-1 text-[12px] text-ink-faint">under data/raw, any session folder</p>
        </Card>
        <Card title="Manifests">
          {s ? (
            <p className="data text-3xl font-semibold">{s.manifests}</p>
          ) : (
            <LoadError error={stats.error} loading={stats.loading} />
          )}
          <p className="mt-1 text-[12px] text-ink-faint">under data/manifests</p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Datasets">
          {datasets.loading && !datasets.data ? (
            <LoadError error={datasets.error} loading />
          ) : datasets.data && datasets.data.length > 0 ? (
            <ul className="divide-y divide-line/60">
              {datasets.data.map((d) => (
                <li key={d.dataset_id} className="flex items-center justify-between gap-3 py-2">
                  <div>
                    <p className="text-[13px] font-medium">{d.name}</p>
                    <p className="data text-[11px] text-ink-faint">{d.path}</p>
                  </div>
                  <StatusBadge tone="neutral">{d.clip_count} clips</StatusBadge>
                </li>
              ))}
            </ul>
          ) : (
            <div className="space-y-2">
              <Empty text="No datasets yet." />
              <p className="text-[12px] text-ink-faint">
                Clips and manifests appear here once you record them (recording UI arrives in
                Phase 4). Nothing is simulated.
              </p>
            </div>
          )}
        </Card>

        <Card title="Distribution">
          {s ? (
            classes.length === 0 && modalities.length === 0 ? (
              <Empty text="No labeled clips yet — distribution is empty, not zero-filled." />
            ) : (
              <div className="space-y-3">
                {classes.length > 0 && (
                  <div>
                    <p className="label mb-1.5">By class</p>
                    <div className="flex flex-wrap gap-1.5">
                      {classes.map(([k, v]) => (
                        <span key={k} className="data border border-line px-1.5 py-0.5 text-[11px]">
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {modalities.length > 0 && (
                  <div>
                    <p className="label mb-1.5">By modality</p>
                    <div className="flex flex-wrap gap-1.5">
                      {modalities.map(([k, v]) => (
                        <span key={k} className="data border border-line px-1.5 py-0.5 text-[11px]">
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          ) : (
            <LoadError error={stats.error} loading={stats.loading} />
          )}
        </Card>
      </div>

      <p className="flex items-center gap-1.5 text-[13px] text-ink-faint">
        <FileVideo size={14} aria-hidden />
        Splits are participant/session-based and stored under data/splits — enforced in Phase 4,
        never random row splits.
      </p>
      <p className="flex items-center gap-1.5 text-[13px] text-ink-faint">
        <Database size={14} aria-hidden />
        All numbers on this page are counted from real files in the project data directory.
      </p>
    </div>
  );
}
