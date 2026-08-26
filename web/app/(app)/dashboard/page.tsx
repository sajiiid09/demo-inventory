import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { Metrics } from "@/lib/types";

export default async function DashboardPage() {
  const m = await api.get<Metrics>("/dashboard/metrics");

  const cards: { label: string; value: string; hint?: string }[] = [
    { label: "Total members", value: String(m.members_total), hint: "active only" },
    { label: "Active loans", value: String(m.loans_active), hint: "DISBURSED" },
    { label: "Total disbursed", value: money(m.disbursed_total), hint: "all-time, ledger" },
    { label: "Total collections", value: money(m.collected_total), hint: "includes fees" },
    { label: "Total outstanding", value: money(m.outstanding_total), hint: "excludes fees" },
  ];

  return (
    <div>
      <h1 className="text-xl font-semibold">Dashboard</h1>
      <p className="mt-1 text-sm text-gray-500">
        Each figure is one SQL query — reproducible in psql (DATABASE.md §5).
      </p>
      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        {cards.map((c) => (
          <div key={c.label} className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-gray-500">{c.label}</p>
            <p className="mt-2 text-xl font-semibold tabular-nums">{c.value}</p>
            {c.hint && <p className="mt-1 text-[11px] text-gray-400">{c.hint}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
