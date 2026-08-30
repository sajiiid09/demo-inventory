/**
 * A figure with its label. Deliberately borderless — the parent grid draws the
 * hairlines with `gap-px bg-rule`, which keeps rules crisp at any wrap point
 * instead of doubling up where cards meet.
 *
 * Use with: <div className="grid gap-px border border-rule bg-rule …">
 */
export function StatCard({
  label,
  value,
  hint,
  className = "",
}: {
  label: string;
  value: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={`bg-paper p-4 ${className}`}>
      <p className="text-micro uppercase text-ink-muted">{label}</p>
      <p className="mt-2 text-figure font-medium tnum">{value}</p>
      {hint && <p className="mt-1 text-micro text-ink-faint">{hint}</p>}
    </div>
  );
}
