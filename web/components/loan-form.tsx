"use client";

/**
 * The loan form with a LIVE preview: it calls POST /loans/preview directly
 * (credentials included) so the officer can show the customer the exact
 * installment before anything is saved. The preview writes nothing (ADR-003).
 */

import { useState } from "react";

import { createLoan } from "@/lib/actions";
import type { MemberListItem, Preview } from "@/lib/types";
import { money } from "@/lib/format";

const field = "mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm";

export function LoanForm({ members }: { members: MemberListItem[] }) {
  const [form, setForm] = useState({
    member_id: members[0]?.id ?? "",
    principal: "100000.00",
    interest_rate_annual: "12.00",
    term_count: "24",
    frequency: "WEEKLY",
    late_fee: "100.00",
    grace_days: "3",
    applied_on: "2026-01-02",
  });
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm({ ...form, [key]: e.target.value });
  }

  async function refreshPreview() {
    setPreviewError(null);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/loans/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            principal: form.principal,
            interest_rate_annual: form.interest_rate_annual,
            term_count: Number(form.term_count),
            frequency: form.frequency,
            start_date: form.applied_on,
          }),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail?.message ?? "Preview failed.");
      }
      setPreview(await res.json());
    } catch (err) {
      setPreview(null);
      setPreviewError(err instanceof Error ? err.message : "Preview failed.");
    }
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <form action={createLoan} className="space-y-3 text-sm">
        <label className="block">
          <span className="text-gray-700">Member</span>
          <select name="member_id" value={form.member_id} onChange={set("member_id")} className={field}>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.member_code} · {m.full_name}
              </option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-gray-700">Principal</span>
            <input name="principal" value={form.principal} onChange={set("principal")} className={field} />
          </label>
          <label className="block">
            <span className="text-gray-700">Rate %/yr (flat)</span>
            <input
              name="interest_rate_annual"
              value={form.interest_rate_annual}
              onChange={set("interest_rate_annual")}
              className={field}
            />
          </label>
          <label className="block">
            <span className="text-gray-700">Installments</span>
            <input name="term_count" value={form.term_count} onChange={set("term_count")} className={field} />
          </label>
          <label className="block">
            <span className="text-gray-700">Frequency</span>
            <select name="frequency" value={form.frequency} onChange={set("frequency")} className={field}>
              <option value="WEEKLY">Weekly</option>
              <option value="MONTHLY">Monthly</option>
            </select>
          </label>
          <label className="block">
            <span className="text-gray-700">Late fee</span>
            <input name="late_fee" value={form.late_fee} onChange={set("late_fee")} className={field} />
          </label>
          <label className="block">
            <span className="text-gray-700">Grace days</span>
            <input name="grace_days" value={form.grace_days} onChange={set("grace_days")} className={field} />
          </label>
        </div>
        <label className="block">
          <span className="text-gray-700">Applied on</span>
          <input name="applied_on" value={form.applied_on} onChange={set("applied_on")} className={field} />
        </label>
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={refreshPreview}
            className="rounded border border-gray-300 px-3 py-1.5 font-medium hover:bg-gray-100"
          >
            Preview schedule
          </button>
          <button
            type="submit"
            className="rounded bg-gray-900 px-3 py-1.5 font-medium text-white hover:bg-gray-700"
          >
            Create application
          </button>
        </div>
      </form>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-xs uppercase tracking-wide text-gray-500">Live preview (writes nothing)</p>
        {previewError && <p className="mt-2 text-sm text-red-600">{previewError}</p>}
        {!preview && !previewError && (
          <p className="mt-2 text-sm text-gray-400">Press “Preview schedule” to see the numbers.</p>
        )}
        {preview && (
          <>
            <dl className="mt-3 space-y-1 text-sm">
              <Row label="Interest" value={money(preview.total_interest)} />
              <Row label="Total payable" value={money(preview.total_payable)} strong />
              <Row label="Per installment" value={money(preview.installment_amount)} strong />
            </dl>
            <table className="mt-3 w-full text-xs">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500">
                  <th className="py-1">#</th>
                  <th className="py-1">Due</th>
                  <th className="py-1 text-right">Principal</th>
                  <th className="py-1 text-right">Interest</th>
                  <th className="py-1 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {preview.schedule.slice(0, 3).map((r) => (
                  <tr key={r.seq} className="border-b border-gray-100">
                    <td className="py-1">{r.seq}</td>
                    <td className="py-1">{r.due_date}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.principal_due)}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.interest_due)}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.amount_due)}</td>
                  </tr>
                ))}
                {preview.schedule.length > 6 && (
                  <tr className="text-gray-400">
                    <td colSpan={5} className="py-1 text-center">
                      … {preview.schedule.length - 4} more …
                    </td>
                  </tr>
                )}
                {preview.schedule.slice(-1).map((r) => (
                  <tr key={r.seq} className="border-b border-gray-100">
                    <td className="py-1">{r.seq}</td>
                    <td className="py-1">{r.due_date}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.principal_due)}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.interest_due)}</td>
                    <td className="py-1 text-right tabular-nums">{money(r.amount_due)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className={`tabular-nums ${strong ? "font-semibold" : ""}`}>{value}</dd>
    </div>
  );
}
