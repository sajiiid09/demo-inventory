import { notFound } from "next/navigation";

import { buttonClass } from "@/components/ui/button";
import { DetailItem, DetailSection, FactList } from "@/components/ui/detail";
import { DisclosureRow } from "@/components/ui/disclosure-row";
import { fieldClass } from "@/components/ui/field";
import { Meter } from "@/components/ui/meter";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status";
import { Num, Table, Td, Th } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { approveLoan, disburseLoan, recordRepayment, rejectLoan } from "@/lib/actions";
import {
  formatDate,
  formatDateShort,
  isOverdue,
  money,
  num,
  relativeDate,
  todayISO,
} from "@/lib/format";
import type { LoanDetail, ScheduleRow, SettlementQuote, User } from "@/lib/types";

const SCHEDULE_COLS = 6;

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

  // One clock reading for the whole page, so every relative string agrees.
  const now = new Date();
  const paidCount = loan.schedule.filter((r) => r.status === "PAID").length;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-lg font-medium tracking-tight">{loan.loan_code}</h1>
        <StatusBadge status={loan.status} />
      </div>
      <p className="mt-1.5 text-sm text-ink-muted">
        {loan.member.full_name}{" "}
        <span className="font-mono text-micro text-ink-faint">{loan.member.member_code}</span>
      </p>

      {sp.error && (
        <p className="mt-4 border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
          {sp.error}
        </p>
      )}

      <div className="mt-8 grid grid-cols-2 gap-px border border-rule bg-rule md:grid-cols-4">
        <StatCard label="Principal" value={money(loan.terms.principal)} />
        <StatCard
          label="Total payable"
          value={money(loan.totals.total_payable)}
          hint={
            loan.totals.total_interest
              ? `incl. ${money(loan.totals.total_interest)} interest`
              : "frozen at disbursement"
          }
        />
        <StatCard
          label="Paid so far"
          value={money(loan.totals.paid_total)}
          hint="principal + interest + fees"
        />
        <StatCard
          label="Outstanding"
          value={money(loan.totals.outstanding)}
          hint={`+ ${money(loan.totals.accrued_fees)} fees accrued`}
        />
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
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
            ["Applied", formatDateShort(loan.dates.applied_on)],
            ["Disbursed", formatDateShort(loan.dates.disbursed_on)],
            ["Closed", formatDateShort(loan.dates.closed_at?.slice(0, 10))],
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
        <section className="mt-10">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="text-micro uppercase text-ink-muted">Schedule</h2>
            <p className="text-micro uppercase text-ink-faint">
              {loan.schedule.length} installments · {paidCount} paid
            </p>
          </div>

          <div className="mt-3">
            <Table className="min-w-[34rem]">
              <thead>
                <tr>
                  <Th className="w-12">#</Th>
                  <Th>Due</Th>
                  <Th align="right">Amount due</Th>
                  <Th align="right" className="hidden sm:table-cell">
                    Paid
                  </Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {loan.schedule.map((r) => (
                  <ScheduleLine key={r.seq} row={r} now={now} />
                ))}
              </tbody>
            </Table>
          </div>
        </section>
      )}
    </div>
  );
}

function ScheduleLine({ row, now }: { row: ScheduleRow; now: Date }) {
  const paid = num(row.principal_paid) + num(row.interest_paid);
  const due = num(row.amount_due);
  const overdue = isOverdue(row, now);

  return (
    <DisclosureRow
      cols={SCHEDULE_COLS}
      label={`installment ${row.seq}`}
      detail={<ScheduleDetail row={row} paid={paid} />}
    >
      <Td className="tnum text-ink-faint">{String(row.seq).padStart(2, "0")}</Td>
      <Td>
        <span className="whitespace-nowrap tnum">{formatDate(row.due_date)}</span>
        <span className="mt-0.5 block text-micro text-ink-faint">
          {relativeDate(row.due_date, now)}
        </span>
      </Td>
      <Num>{money(row.amount_due)}</Num>
      <Num className="hidden sm:table-cell">
        {money(paid)}
        <Meter
          className="mt-1.5"
          value={paid}
          total={due}
          label={`${money(paid)} of ${money(row.amount_due)} paid`}
        />
      </Num>
      <Td>
        <StatusBadge status={overdue ? "OVERDUE" : row.status} />
      </Td>
    </DisclosureRow>
  );
}

/**
 * Everything the resting row leaves out — including two things the UI never
 * showed at all: `fee_paid`, and the per-receipt `allocations` the API has always
 * sent but the TypeScript interface used to drop.
 */
function ScheduleDetail({ row, paid }: { row: ScheduleRow; paid: number }) {
  const principalOwed = num(row.principal_due) - num(row.principal_paid);
  const interestOwed = num(row.interest_due) - num(row.interest_paid);

  return (
    <div className="grid gap-8 md:grid-cols-2">
      <DetailSection title="Breakdown">
        <dl>
          <DetailItem
            label="Principal"
            value={`${money(row.principal_due)} · paid ${money(row.principal_paid)}`}
          />
          <DetailItem
            label="Interest"
            value={`${money(row.interest_due)} · paid ${money(row.interest_paid)}`}
          />
          <DetailItem
            label="Late fee"
            value={`${money(row.accrued_fee)} owed · paid ${money(row.fee_paid)}`}
          />
          <DetailItem
            label="Still owed"
            value={money(principalOwed + interestOwed)}
            strong
          />
        </dl>
        <p className="mt-2 text-micro text-ink-faint">
          Accrued fees sit outside outstanding — a fee is not a receivable until it is
          charged (DOMAIN.md §1).
        </p>
      </DetailSection>

      <DetailSection title={`Repayments (${row.allocations.length})`}>
        {row.allocations.length === 0 ? (
          <p className="border border-dashed border-rule px-3 py-4 text-xs text-ink-faint">
            Nothing has been allocated to this installment yet.
          </p>
        ) : (
          <div className="border border-rule">
            <div className="grid grid-cols-4 gap-2 border-b border-rule bg-paper-muted px-3 py-1.5 text-micro uppercase text-ink-faint">
              <span>Receipt</span>
              <span className="text-right">Fee</span>
              <span className="text-right">Interest</span>
              <span className="text-right">Principal</span>
            </div>
            {row.allocations.map((a) => (
              <div
                key={a.receipt_no}
                className="grid grid-cols-4 gap-2 border-b border-rule px-3 py-2 text-xs last:border-b-0"
              >
                <span className="font-mono">{a.receipt_no}</span>
                <span className="text-right tnum">{money(a.fee)}</span>
                <span className="text-right tnum">{money(a.interest)}</span>
                <span className="text-right tnum">{money(a.principal)}</span>
              </div>
            ))}
            <div className="grid grid-cols-4 gap-2 border-t border-ink px-3 py-2 text-xs font-medium">
              <span className="uppercase text-ink-muted">Total</span>
              <span className="col-span-3 text-right tnum">{money(paid + num(row.fee_paid))}</span>
            </div>
          </div>
        )}
        <p className="mt-2 text-micro text-ink-faint">
          Every payment is applied fee → interest → principal (DOMAIN.md §3).
        </p>
      </DetailSection>
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
    <div className="mt-6 border border-rule bg-paper p-5">
      <p className="text-micro uppercase text-ink-muted">Actions</p>

      <div className="mt-4 flex flex-wrap items-start gap-x-8 gap-y-5">
        {canApprove && (
          <form action={approveLoan}>
            <input type="hidden" name="loan_id" value={loan.id} />
            <button className={buttonClass("primary")}>Approve</button>
          </form>
        )}

        {canDisburse && (
          <form action={disburseLoan} className="flex items-end gap-2">
            <input type="hidden" name="loan_id" value={loan.id} />
            <label className="block">
              <span className="text-micro uppercase text-ink-muted">Disburse on</span>
              <input
                name="disbursed_on"
                type="date"
                required
                defaultValue={todayISO()}
                className={`${fieldClass} w-44`}
              />
            </label>
            <button className={buttonClass("primary")}>Disburse</button>
          </form>
        )}

        {canCollect && quote && (
          <form action={recordRepayment} className="flex flex-wrap items-end gap-2">
            <input type="hidden" name="loan_id" value={loan.id} />
            <label className="block">
              <span className="text-micro uppercase text-ink-muted">Amount</span>
              <input
                name="amount"
                required
                defaultValue={quote.settlement_total}
                className={`${fieldClass} w-36 tnum`}
              />
            </label>
            <label className="block">
              <span className="text-micro uppercase text-ink-muted">Paid on</span>
              <input
                name="paid_on"
                type="date"
                required
                defaultValue={todayISO()}
                className={`${fieldClass} w-44`}
              />
            </label>
            <label className="block">
              <span className="text-micro uppercase text-ink-muted">Method</span>
              <select name="method" className={`${fieldClass} w-32`}>
                <option>CASH</option>
                <option>BANK</option>
                <option>MOBILE</option>
              </select>
            </label>
            <button className={buttonClass("primary")}>Record repayment</button>
            <p className="w-full text-micro text-ink-faint">
              Settlement today {money(quote.settlement_total)} — outstanding{" "}
              {money(quote.outstanding)} plus {money(quote.accrued_fees)} fees.
            </p>
          </form>
        )}
      </div>

      {canReject && (
        /* Destructive action, separated from the rest by a rule so it is never a mis-click. */
        <form action={rejectLoan} className="mt-5 flex flex-wrap items-end gap-2 border-t border-rule pt-5">
          <input type="hidden" name="loan_id" value={loan.id} />
          <label className="block">
            <span className="text-micro uppercase text-ink-muted">Rejection reason</span>
            <input
              name="reason"
              required
              aria-label="Rejection reason"
              placeholder="Why is this being rejected?"
              className={`${fieldClass} w-72`}
            />
          </label>
          <button className={buttonClass("danger")}>Reject</button>
        </form>
      )}
    </div>
  );
}
