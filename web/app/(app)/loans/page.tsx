import Link from "next/link";

import { api } from "@/lib/api";
import { money, statusClass } from "@/lib/format";
import type { LoanListItem, Page } from "@/lib/types";

const FILTERS = ["ALL", "PENDING", "APPROVED", "DISBURSED", "CLOSED", "REJECTED"];

export default async function LoansPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; q?: string }>;
}) {
  const sp = await searchParams;
  const params = new URLSearchParams();
  if (sp.status && sp.status !== "ALL") params.set("status", sp.status);
  if (sp.q) params.set("q", sp.q);
  const page = await api.get<Page<LoanListItem>>(`/loans${params.size ? `?${params}` : ""}`);

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Loans</h1>
        <Link
          href="/loans/new"
          className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700"
        >
          New loan
        </Link>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={f === "ALL" ? "/loans" : `/loans?status=${f}`}
            className={`rounded-full px-3 py-1 text-xs ${
              (sp.status ?? "ALL") === f
                ? "bg-gray-900 text-white"
                : "border border-gray-300 text-gray-600 hover:bg-gray-100"
            }`}
          >
            {f}
          </Link>
        ))}
      </div>

      <table className="mt-4 w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="py-2">Code</th>
            <th className="py-2">Member</th>
            <th className="py-2 text-right">Principal</th>
            <th className="py-2 text-right">Total payable</th>
            <th className="py-2 text-right">Outstanding</th>
            <th className="py-2">Next due</th>
            <th className="py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((l) => (
            <tr key={l.id} className="border-b border-gray-100">
              <td className="py-2">
                <Link href={`/loans/${l.id}`} className="font-mono text-xs underline">
                  {l.loan_code}
                </Link>
              </td>
              <td className="py-2">
                {l.member.full_name}{" "}
                <span className="font-mono text-xs text-gray-400">{l.member.member_code}</span>
              </td>
              <td className="py-2 text-right tabular-nums">{money(l.principal)}</td>
              <td className="py-2 text-right tabular-nums">{money(l.total_payable)}</td>
              <td className="py-2 text-right tabular-nums">{money(l.outstanding)}</td>
              <td className="py-2">{l.next_due_date ?? "—"}</td>
              <td className="py-2">
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(l.status)}`}>
                  {l.status}
                </span>
              </td>
            </tr>
          ))}
          {page.items.length === 0 && (
            <tr>
              <td colSpan={7} className="py-6 text-center text-gray-400">
                No loans match.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-gray-400">{page.total} total</p>
    </div>
  );
}
