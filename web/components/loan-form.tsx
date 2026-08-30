"use client";

/**
 * The loan form with a LIVE preview: it calls POST /loans/preview directly
 * (credentials included) so the officer can show the customer the exact
 * installment before anything is saved. The preview writes nothing (ADR-003).
 */

import { Fragment, useState } from "react";

import { buttonClass } from "@/components/ui/button";
import { fieldClass } from "@/components/ui/field";
import { ChevronRight } from "@/components/ui/icons";
import { createLoan } from "@/lib/actions";
import { apiBaseUrl } from "@/lib/api-url";
import { formatDateShort, money } from "@/lib/format";
import type { MemberListItem, Preview } from "@/lib/types";

const COLLAPSED_HEAD = 3;
const COLLAPSED_TAIL = 1;

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
  const [showAll, setShowAll] = useState(false);

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm({ ...form, [key]: e.target.value });
  }

  async function refreshPreview() {
    setPreviewError(null);
    try {
      const res = await fetch(`${apiBaseUrl()}/loans/preview`, {
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
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail?.message ?? "Preview failed.");
      }
      setPreview(await res.json());
      setShowAll(false);
    } catch (err) {
      setPreview(null);
      setPreviewError(err instanceof Error ? err.message : "Preview failed.");
    }
  }

  // Collapsed shows head + tail; the elided middle is now reachable rather than
  // silently dropped, which also removes the old off-by-two in the "… N more …" guard.
  const rows = preview?.schedule ?? [];
  const collapsible = rows.length > COLLAPSED_HEAD + COLLAPSED_TAIL;
  const visible =
    !collapsible || showAll
      ? rows
      : [...rows.slice(0, COLLAPSED_HEAD), ...rows.slice(-COLLAPSED_TAIL)];
  const hiddenCount = rows.length - COLLAPSED_HEAD - COLLAPSED_TAIL;

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <form action={createLoan} className="space-y-4 border border-rule p-5">
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Member</span>
          <select
            name="member_id"
            value={form.member_id}
            onChange={set("member_id")}
            className={fieldClass}
          >
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.member_code} · {m.full_name}
              </option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Principal</span>
            <input
              name="principal"
              value={form.principal}
              onChange={set("principal")}
              className={`${fieldClass} tnum`}
            />
          </label>
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Rate %/yr (flat)</span>
            <input
              name="interest_rate_annual"
              value={form.interest_rate_annual}
              onChange={set("interest_rate_annual")}
              className={`${fieldClass} tnum`}
            />
          </label>
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Installments</span>
            <input
              name="term_count"
              value={form.term_count}
              onChange={set("term_count")}
              className={`${fieldClass} tnum`}
            />
          </label>
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Frequency</span>
            <select
              name="frequency"
              value={form.frequency}
              onChange={set("frequency")}
              className={fieldClass}
            >
              <option value="WEEKLY">Weekly</option>
              <option value="MONTHLY">Monthly</option>
            </select>
          </label>
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Late fee</span>
            <input
              name="late_fee"
              value={form.late_fee}
              onChange={set("late_fee")}
              className={`${fieldClass} tnum`}
            />
          </label>
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Grace days</span>
            <input
              name="grace_days"
              value={form.grace_days}
              onChange={set("grace_days")}
              className={`${fieldClass} tnum`}
            />
          </label>
        </div>

        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Applied on</span>
          <input
            name="applied_on"
            value={form.applied_on}
            onChange={set("applied_on")}
            className={`${fieldClass} tnum`}
          />
        </label>

        <div className="flex gap-2 border-t border-rule pt-4">
          <button type="button" onClick={refreshPreview} className={buttonClass("secondary")}>
            Preview schedule
          </button>
          <button type="submit" className={buttonClass("primary")}>
            Create application
          </button>
        </div>
      </form>

      <div className="border border-rule p-5">
        <p className="text-micro uppercase text-ink-muted">Live preview — writes nothing</p>

        {previewError && (
          <p className="mt-3 border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
            {previewError}
          </p>
        )}
        {!preview && !previewError && (
          <p className="mt-3 text-sm text-ink-faint">
            Press “Preview schedule” to see the numbers.
          </p>
        )}

        {preview && (
          <>
            <dl className="mt-4">
              <Row label="Interest" value={money(preview.total_interest)} />
              <Row label="Total payable" value={money(preview.total_payable)} strong />
              <Row label="Per installment" value={money(preview.installment_amount)} strong />
            </dl>

            <table className="mt-5 w-full border-collapse text-xs">
              <thead>
                <tr className="border-y border-ink text-left text-micro uppercase text-ink-muted">
                  <th className="py-1.5 pr-2 font-medium">#</th>
                  <th className="py-1.5 pr-2 font-medium">Due</th>
                  <th className="py-1.5 pr-2 text-right font-medium">Principal</th>
                  <th className="py-1.5 pr-2 text-right font-medium">Interest</th>
                  <th className="py-1.5 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r, i) => (
                  <Fragment key={r.seq}>
                    {collapsible && !showAll && i === COLLAPSED_HEAD && (
                      <tr className="border-b border-rule">
                        <td colSpan={5} className="py-1.5">
                          <button
                            type="button"
                            onClick={() => setShowAll(true)}
                            className="inline-flex cursor-pointer items-center gap-1.5 text-micro uppercase text-ink-muted transition-colors duration-150 hover:text-ink"
                          >
                            <ChevronRight size={10} />
                            Show {hiddenCount} more installments
                          </button>
                        </td>
                      </tr>
                    )}
                    <tr className="border-b border-rule">
                      <td className="py-1.5 pr-2 tnum text-ink-faint">
                        {String(r.seq).padStart(2, "0")}
                      </td>
                      <td className="py-1.5 pr-2 tnum">{formatDateShort(r.due_date)}</td>
                      <td className="py-1.5 pr-2 text-right tnum">{money(r.principal_due)}</td>
                      <td className="py-1.5 pr-2 text-right tnum">{money(r.interest_due)}</td>
                      <td className="py-1.5 text-right tnum">{money(r.amount_due)}</td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>

            {collapsible && showAll && (
              <button
                type="button"
                onClick={() => setShowAll(false)}
                className="mt-3 cursor-pointer text-micro uppercase text-ink-muted transition-colors duration-150 hover:text-ink"
              >
                Collapse schedule
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-1.5 last:border-b-0">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className={`text-data tnum ${strong ? "font-medium" : ""}`}>{value}</dd>
    </div>
  );
}
