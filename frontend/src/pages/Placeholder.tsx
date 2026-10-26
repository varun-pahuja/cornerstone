/**
 * Honest stub for pages whose backend feature is not implemented yet.
 * Never renders fake data or non-functional controls.
 */
export function Placeholder({
  title,
  phase,
  note,
}: {
  title: string;
  phase: string;
  note: string;
}) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      <section className="border border-dashed border-line-strong bg-panel p-8 text-center">
        <p className="label mb-2">Not implemented yet</p>
        <p className="text-[13px] text-ink-soft">
          {note}
        </p>
        <p className="mt-3 data text-xs text-ink-faint">{phase}</p>
      </section>
    </div>
  );
}
