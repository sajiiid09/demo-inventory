/** Label/value layout shared by the disclosure drawers and the fact panels. */

export function DetailSection({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={className}>
      <h4 className="text-micro uppercase text-ink-faint">{title}</h4>
      <div className="mt-2">{children}</div>
    </section>
  );
}

export function DetailItem({
  label,
  value,
  strong = false,
  muted = false,
}: {
  label: string;
  value: React.ReactNode;
  strong?: boolean;
  muted?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-1.5 last:border-b-0">
      <dt className={`text-xs ${muted ? "text-ink-faint" : "text-ink-muted"}`}>{label}</dt>
      <dd className={`text-data tnum ${strong ? "font-medium text-ink" : "text-ink"}`}>{value}</dd>
    </div>
  );
}

export function FactList({
  title,
  rows,
}: {
  title: string;
  rows: [string, React.ReactNode][];
}) {
  return (
    <div className="border border-rule bg-paper p-4">
      <p className="text-micro uppercase text-ink-muted">{title}</p>
      <dl className="mt-2">
        {rows.map(([k, v]) => (
          <DetailItem key={k} label={k} value={v} />
        ))}
      </dl>
    </div>
  );
}
