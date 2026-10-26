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

export function LoadError({ error, loading }: { error: string | null; loading: boolean }) {
  if (loading) return <p className="text-[13px] text-ink-faint">Loading…</p>;
  if (error) return <p className="text-[13px] text-danger">{error}</p>;
  return <p className="text-[13px] text-ink-faint">Unavailable</p>;
}
