import { StatCard } from "@/components/ui/stat-card";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { Metrics } from "@/lib/types";

export default async function DashboardPage() {
  const m = await api.get<Metrics>("/dashboard/metrics");

  const cards: { label: string; value: string; hint?: string; className?: string }[] = [
    { label: "Total members", value: String(m.members_total), hint: "active only" },
    { label: "Active loans", value: String(m.loans_active), hint: "DISBURSED" },
    { label: "Total disbursed", value: money(m.disbursed_total), hint: "all-time, ledger" },
    { label: "Total collections", value: money(m.collected_total), hint: "includes fees" },
    {
      label: "Total outstanding",
      value: money(m.outstanding_total),
      hint: "excludes fees",
      // Odd card out of five — span the full width rather than leave a hole at 2-up.
      className: "col-span-2 md:col-span-1",
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-medium tracking-tight">Dashboard</h1>
      <p className="mt-1 max-w-prose text-sm text-ink-muted">
        Each figure is one SQL query — reproducible in psql (DATABASE.md §5).
      </p>

      {/* gap-px over a rule-coloured ground draws the hairlines; no doubled borders. */}
      <div className="mt-8 grid grid-cols-2 gap-px border border-rule bg-rule md:grid-cols-5">
        {cards.map((c) => (
          <StatCard
            key={c.label}
            label={c.label}
            value={c.value}
            hint={c.hint}
            className={c.className}
          />
        ))}
      </div>
    </div>
  );
}
