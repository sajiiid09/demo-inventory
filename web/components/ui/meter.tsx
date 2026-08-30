/**
 * A 2px progress rule. Deliberately monochrome even when the row is overdue —
 * the red accent stays rare, carried by the badge and the row's left border.
 */
export function Meter({
  value,
  total,
  className = "",
  label,
}: {
  value: number;
  total: number;
  className?: string;
  label?: string;
}) {
  const pct = total > 0 ? Math.min(100, Math.max(0, (value / total) * 100)) : 0;
  return (
    <div
      className={`h-0.5 w-full bg-rule ${className}`}
      role="img"
      aria-label={label ?? `${Math.round(pct)}% paid`}
    >
      <div className="h-full bg-ink" style={{ width: `${pct}%` }} />
    </div>
  );
}
