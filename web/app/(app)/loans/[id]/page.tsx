import { notFound } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import {
  approveLoan,
  disburseLoan,
  recordRepayment,
  rejectLoan,
} from "@/lib/actions";
import { money, statusClass } from "@/lib/format";
import type { LoanDetail, SettlementQuote, User } from "@/lib/types";

const field = "mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm";

export default async function LoanDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;

  let loan: LoanDetail;
  let me: User;
  try {
    [loan, me] = await Promise.all([
      api.get<LoanDetail>(`/loans/${id}`),
      api.get<User>("/auth/me"),
    ]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  const quote =
    loan.status === "DISBURSED"
      ? await api.get<SettlementQuote>(`/loans/${id}/settlement-quote`)
      : null;

  const isCreator = loan.people.created_by.startsWith(me.full_name);

  return (
    <div>
      <div className="flex items-center gap-3">
        <h1 className="font-mono text-lg font-semibold">{loan.loan_code}</h1>
        <span className={`rounded-full px-2 py-0.5 text-xs ${statusClass(loan.status)}`}>
          {loan.status}
        </span>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        {loan.member.full_name} · {loan.member.member_code}
      </p>

      {sp.error && (
        <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{sp.error}</p>
      )}

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Principal" value={money(loan.terms.principal)} />
        <Card
          label="Total payable"
          value={money(loan.totals.total_payable)}
          hint={loan.totals.total_interest ? `incl. ${money(loan.totals.total_interest)} interest` : "frozen at disbursement"}
        />
        <Card
          label="Paid so far"
          value={money(loan.totals.paid_total)}
          hint="principal + interest + fees"
        />
        <Card
          label="Outstanding"
          value={money(loan.totals.outstanding)}
          hint={`+ ${money(loan.totals.accrued_fees)} fees accrued`}
        />
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-3">
        <FactList
          title="Terms"
          rows={[
            ["Rate (flat/yr)", `${loan.terms.interest_rate_annual}%`],
            ["Term", `${loan.terms.term_count} × ${loan.terms.frequency.toLowerCase()}`],
            ["Installment", money(loan.totals.installment_amount)],
            ["Late fee / grace", `${money(loan.terms.late_fee)} / ${loan.terms.grace_days}d`],
          ]}
        />
        <FactList
          title="Dates"
          rows={[
            ["Applied", loan.dates.applied_on],
            ["Disbursed", loan.dates.disbursed_on ?? "—"],
            ["Closed", loan.dates.closed_at?.slice(0, 10) ?? "—"],
          ]}
        />
        <FactList
          title="People"
          rows={[
            ["Created by", loan.people.created_by],
            ["Approved by", loan.people.approved_by ?? "—"],
            ["Disbursed by", loan.people.disbursed_by ?? "—"],
          ]}
        />
      </div>

      <Actions loan={loan} me={me} isCreator={isCreator} quote={quote} />

      {loan.schedule.length > 0 && (
        <>
          <h2 className="mt-8 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Schedule
          </h2>
          <table className="mt-2 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
                <th className="py-2">#</th>
                <th className="py-2">Due</th>
                <th className="py-2 text-right">Principal due</th>
                <th className="py-2 text-right">Interest due</th>
                <th className="py-2 text-right">Amount due</th>
                <th className="py-2 text-right">Paid</th>
                <th className="py-2 text-right">Fee owed</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {loan.schedule.map((r) => (
                <tr key={r.seq} className="border-b border-gray-100">
                  <td className="py-1.5">{r.seq}</td>
                  <td className="py-1.5">{r.due_date}</td>
                  <td className="py-1.5 text-right tabular-nums">{money(r.principal_due)}</td>
                  <td className="py-1.5 text-right tabular-nums">{money(r.interest_due)}</td>
                  <td className="py-1.5 text-right tabular-nums">{money(r.amount_due)}</td>
                  <td className="py-1.5 text-right tabular-nums">
                    {money(String(parseFloat(r.principal_paid) + parseFloat(r.interest_paid)))}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{money(r.accrued_fee)}</td>
                  <td className="py-1.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${statusClass(r.status)}`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function Actions({
  loan,
  me,
  isCreator,
  quote,
}: {
  loan: LoanDetail;
  me: User;
  isCreator: boolean;
  quote: SettlementQuote | null;
}) {
  const canApprove = me.role === "ADMIN" && loan.status === "PENDING" && !isCreator;
  const canReject = me.role === "ADMIN" && loan.status === "PENDING";
  const canDisburse =
    (me.role === "CASHIER" || me.role === "ADMIN") && loan.status === "APPROVED";
  const canCollect =
    (me.role === "CASHIER" || me.role === "ADMIN") && loan.status === "DISBURSED";

  if (!canApprove && !canReject && !canDisburse && !canCollect) return null;

  return (
    <div className="mt-6 flex flex-wrap items-start gap-4 rounded-lg border border-gray-200 bg-white p-4">
      {canApprove && (
        <form action={approveLoan}>
          <input type="hidden" name="loan_id" value={loan.id} />
          <button className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500">
            Approve
          </button>
        </form>
      )}
      {canReject && (
        <form action={rejectLoan} className="flex gap-2">
          <input type="hidden" name="loan_id" value={loan.id} />
          <input
            name="reason"
            required
            aria-label="Rejection reason"
            placeholder="Rejection reason…"
            className="rounded border border-gray-300 px-3 py-1.5 text-sm"
          />
          <button className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500">
            Reject
          </button>
        </form>
      )}
      {canDisburse && (
        <form action={disburseLoan} className="flex items-end gap-2">
          <input type="hidden" name="loan_id" value={loan.id} />
          <label className="text-sm">
            <span className="text-gray-600">Disburse on</span>
            <input name="disbursed_on" type="date" required defaultValue={today()} className={field} />
          </label>
          <button className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700">
            Disburse
          </button>
        </form>
      )}
      {canCollect && quote && (
        <form action={recordRepayment} className="flex items-end gap-2">
          <input type="hidden" name="loan_id" value={loan.id} />
          <label className="text-sm">
            <span className="text-gray-600">Amount</span>
            <input name="amount" required defaultValue={quote.settlement_total} className={field} />
          </label>
          <label className="text-sm">
            <span className="text-gray-600">Paid on</span>
            <input name="paid_on" type="date" required defaultValue={today()} className={field} />
          </label>
          <label className="text-sm">
            <span className="text-gray-600">Method</span>
            <select name="method" className={field}>
              <option>CASH</option>
              <option>BANK</option>
              <option>MOBILE</option>
            </select>
          </label>
          <button className="rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700">
            Record repayment
          </button>
          <p className="ml-2 text-xs text-gray-400">
            settlement today: {money(quote.settlement_total)} (outstanding{" "}
            {money(quote.outstanding)} + fees {money(quote.accrued_fees)})
          </p>
        </form>
      )}
    </div>
  );
}

// All actions take FormData; hidden inputs carry the loan id.

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function Card({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-gray-400">{hint}</p>}
    </div>
  );
}

function FactList({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</p>
      <dl className="mt-2 space-y-1 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4">
            <dt className="text-gray-500">{k}</dt>
            <dd className="text-right">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
