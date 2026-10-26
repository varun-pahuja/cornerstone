import { SlidersHorizontal, TriangleAlert } from "lucide-react";
import { api } from "../services/api";
import { usePoll } from "../hooks/usePoll";
import { Card, LoadError, Row } from "../components/ui/Card";
import { StatusBadge } from "../components/ui/StatusBadge";

export default function Calibration() {
  const settings = usePoll(() => api.getSettings(), 30_000);
  const s = settings.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Calibration</h1>
        <StatusBadge tone="warn">No calibration profile</StatusBadge>
      </div>

      <div className="border border-warn/30 bg-warn-soft px-3 py-2 text-[13px] text-warn">
        Calibration (per-user thresholds, lighting/session adaptation) is not implemented yet —
        it arrives in Phase 9 with a real calibration API. The values below are your current
        configuration defaults, not a measured calibration.
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Current thresholds (config defaults)">
          {s ? (
            <>
              <Row label="Recognition mode" value={s.recognition_mode} />
              <Row label="Sign threshold" value={s.sign_threshold} />
              <Row label="Lip threshold" value={s.lip_threshold} />
              <Row label="Min confidence" value={s.min_confidence} />
              <Row label="Single-modality allowed" value={s.allow_single_modality ? "yes" : "no"} />
            </>
          ) : (
            <LoadError error={settings.error} loading={settings.loading} />
          )}
        </Card>

        <Card title="How calibration will work">
          <ol className="space-y-2 text-[13px] text-ink-soft">
            <li>
              <span className="data mr-2 text-ink-faint">1</span>
              Record a short guided sign set in your usual lighting.
            </li>
            <li>
              <span className="data mr-2 text-ink-faint">2</span>
              System measures per-class confidence distributions.
            </li>
            <li>
              <span className="data mr-2 text-ink-faint">3</span>
              Thresholds are tuned to your distributions and stored as a profile.
            </li>
            <li>
              <span className="data mr-2 text-ink-faint">4</span>
              Profile applies on top of config defaults; you can always override manually.
            </li>
          </ol>
        </Card>
      </div>

      <p className="flex items-center gap-1.5 text-[13px] text-ink-faint">
        <SlidersHorizontal size={14} aria-hidden />
        Until Phase 9, tune thresholds by hand under Device Settings — they take effect
        immediately for fusion.
      </p>
      <p className="flex items-center gap-1.5 text-[13px] text-ink-faint">
        <TriangleAlert size={14} aria-hidden />
        This page never invents a calibration score. Absent a measured profile it says so.
      </p>
    </div>
  );
}
