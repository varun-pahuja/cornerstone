import { cn } from "../../lib/utils";

type Tone = "ok" | "warn" | "danger" | "info" | "primary" | "neutral";

const tones: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok border-ok/25",
  warn: "bg-warn-soft text-warn border-warn/25",
  danger: "bg-danger-soft text-danger border-danger/25",
  info: "bg-info-soft text-info border-info/25",
  primary: "bg-primary-soft text-primary border-primary/30",
  neutral: "bg-elevated text-ink-soft border-line-strong",
};

/**
 * Semantic status pill: uppercase mono + dot, so state is never carried by
 * color alone (dot + text always present).
 */
export function StatusBadge({
  tone,
  children,
  className,
}: {
  tone: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[10.5px] font-medium tracking-[0.06em] uppercase",
        tones[tone],
        className,
      )}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" aria-hidden />
      {children}
    </span>
  );
}
