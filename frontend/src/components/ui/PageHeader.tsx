import { cn } from "../../lib/utils";

/**
 * Page title block: editorial serif heading + quiet description + action slot.
 * One per page — the hierarchy anchor of the Obsidian Instrument direction.
 */
export function PageHeader({
  title,
  description,
  actions,
  status,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  status?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-line pb-4",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="display text-[27px] leading-[1.15] text-ink">{title}</h1>
        {description && (
          <p className="mt-1.5 max-w-[68ch] text-[13px] leading-relaxed text-ink-soft">
            {description}
          </p>
        )}
      </div>
      {(actions || status) && (
        <div className="flex flex-wrap items-center gap-2">
          {status}
          {actions}
        </div>
      )}
    </header>
  );
}
