import { cn } from "../../lib/utils";

export function Card({
  title,
  children,
  className,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-md border border-line bg-panel", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 className="label">{title}</h2>
        {actions}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 py-2 last:border-0">
      <span className="text-[13px] text-ink-soft">{label}</span>
      <span className="data text-right text-[13px] font-medium text-ink">{value}</span>
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <p className="text-[13px] leading-relaxed text-ink-faint">{text}</p>;
}

/** One real backend metric — shown raw, never converted or invented. */
export function MetricCell({ name, value }: { name: string; value: unknown }) {
  const text =
    value === null || value === undefined
      ? "—"
      : typeof value === "number"
        ? Number.isInteger(value)
          ? String(value)
          : value.toFixed(4)
        : String(value);
  return (
    <div className="rounded-sm border border-line bg-rail px-3 py-2">
      <p className="label">{name.replace(/_/g, " ")}</p>
      <p className="data mt-1 text-[15px] font-medium text-ink">{text}</p>
    </div>
  );
}

export function LoadError({ error, loading }: { error: string | null; loading: boolean }) {
  if (loading) return <p className="text-[13px] text-ink-faint">Loading…</p>;
  if (error) return <p className="text-[13px] text-danger">{error}</p>;
  return <p className="text-[13px] text-ink-faint">Unavailable</p>;
}
