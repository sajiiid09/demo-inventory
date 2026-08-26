import Link from "next/link";

import { api } from "@/lib/api";
import { money, statusClass } from "@/lib/format";
import type { MemberListItem, Page } from "@/lib/types";

export default async function MembersPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; ok?: string; error?: string }>;
}) {
  const sp = await searchParams;
  const page = await api.get<Page<MemberListItem>>(
    `/members${sp.q ? `?q=${encodeURIComponent(sp.q)}` : ""}`,
  );

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Members</h1>
        <Link
          href="/members/new"
          className="rounded bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-700"
        >
          Register member
        </Link>
      </div>

      <form className="mt-4 flex gap-2" action="/members">
        <input
          name="q"
          defaultValue={sp.q ?? ""}
          aria-label="Search members"
          placeholder="Search name, phone, or member code…"
          className="w-72 rounded border border-gray-300 px-3 py-1.5 text-sm"
        />
        <button className="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100">
          Search
        </button>
      </form>

      {sp.ok && <p className="mt-3 rounded bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{sp.ok}</p>}
      {sp.error && <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{sp.error}</p>}

      <table className="mt-4 w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="py-2">Code</th>
            <th className="py-2">Name</th>
            <th className="py-2">Phone</th>
            <th className="py-2">Status</th>
            <th className="py-2">Active loan</th>
            <th className="py-2 text-right">Outstanding</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((m) => (
            <tr key={m.id} className="border-b border-gray-100">
              <td className="py-2 font-mono text-xs">{m.member_code}</td>
              <td className="py-2">{m.full_name}</td>
              <td className="py-2">{m.phone}</td>
              <td className="py-2">
                <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(m.status)}`}>
                  {m.status}
                </span>
              </td>
              <td className="py-2 font-mono text-xs">{m.active_loan_code ?? "—"}</td>
              <td className="py-2 text-right tabular-nums">{money(m.outstanding)}</td>
            </tr>
          ))}
          {page.items.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-gray-400">
                No members match.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-gray-400">{page.total} total</p>
    </div>
  );
}
