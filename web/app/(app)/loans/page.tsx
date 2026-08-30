import Link from "next/link";

import { buttonClass } from "@/components/ui/button";
import { DetailItem } from "@/components/ui/detail";
import { DisclosureRow } from "@/components/ui/disclosure-row";
import { fieldClass } from "@/components/ui/field";
import { ArrowRight, Search } from "@/components/ui/icons";
import { Meter } from "@/components/ui/meter";
import { StatusBadge } from "@/components/ui/status";
import { EmptyRow, Num, Table, Td, Th } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDateShort, money, num, relativeDate } from "@/lib/format";
import type { LoanListItem, Page } from "@/lib/types";

const FILTERS = ["ALL", "PENDING", "APPROVED", "DISBURSED", "CLOSED", "REJECTED"];
const COLS = 5;

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

  // Resolved once on the server so every relative string on the page agrees.
  const now = new Date();
  const active = sp.status ?? "ALL";

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-medium tracking-tight">Loans</h1>
        <Link href="/loans/new" className={buttonClass("primary")}>
          New loan
        </Link>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        {/* Square segmented control — active state is a straight inversion. */}
        <div className="flex flex-wrap border border-rule">
          {FILTERS.map((f) => (
            <Link
              key={f}
              href={f === "ALL" ? "/loans" : `/loans?status=${f}`}
              aria-current={active === f ? "true" : undefined}
              className={`border-r border-rule px-3 py-1.5 text-micro uppercase transition-colors duration-150 last:border-r-0 ${
                active === f
                  ? "on-ink bg-ink text-paper"
                  : "text-ink-muted hover:bg-paper-muted hover:text-ink"
              }`}
            >
              {f}
            </Link>
          ))}
        </div>

        <form action="/loans" className="flex gap-2">
          {sp.status && sp.status !== "ALL" && (
            <input type="hidden" name="status" value={sp.status} />
          )}
          <div className="relative">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
              <Search />
            </span>
            <input
              name="q"
              defaultValue={sp.q ?? ""}
              aria-label="Search loans"
              placeholder="Loan code, member name or code…"
              className={`${fieldClass} mt-0 w-64 py-1.5 pl-9`}
            />
          </div>
          <button className={buttonClass("secondary")}>Search</button>
        </form>
      </div>

      <div className="mt-6">
        {/* Below md the wrapper scrolls; the min-width stops columns crushing. */}
        <Table className="min-w-[32rem]">
          <thead>
            <tr>
              <Th>Loan</Th>
              <Th className="hidden sm:table-cell">Next due</Th>
              <Th align="right">Outstanding</Th>
              <Th>Status</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {page.items.map((l) => {
              const payable = num(l.total_payable);
              const repaid = l.total_payable ? payable - num(l.outstanding) : 0;

              return (
                <DisclosureRow
                  key={l.id}
                  cols={COLS}
                  label={`loan ${l.loan_code}`}
                  detail={
                    <div className="max-w-2xl">
                      <dl className="grid gap-x-10 sm:grid-cols-2">
                        <DetailItem label="Principal" value={money(l.principal)} />
                        <DetailItem label="Total payable" value={money(l.total_payable)} />
                        <DetailItem
                          label="Repaid"
                          value={l.total_payable ? money(repaid) : "—"}
                        />
                        <DetailItem label="Outstanding" value={money(l.outstanding)} strong />
                        <DetailItem
                          label="Next due"
                          value={
                            l.next_due_date
                              ? `${formatDateShort(l.next_due_date)} · ${relativeDate(
                                  l.next_due_date,
                                  now,
                                )}`
                              : "—"
                          }
                        />
                        <DetailItem label="Member" value={l.member.full_name} />
                      </dl>

                      {l.total_payable && payable > 0 && (
                        <div className="mt-4">
                          <div className="flex items-baseline justify-between text-micro uppercase text-ink-faint">
                            <span>Repayment progress</span>
                            <span className="tnum">
                              {Math.round((repaid / payable) * 100)}%
                            </span>
                          </div>
                          <Meter
                            className="mt-1.5"
                            value={repaid}
                            total={payable}
                            label={`${money(repaid)} of ${money(l.total_payable)} repaid`}
                          />
                        </div>
                      )}

                      <Link
                        href={`/loans/${l.id}`}
                        className={`${buttonClass("secondary")} mt-5`}
                      >
                        View loan <ArrowRight />
                      </Link>
                    </div>
                  }
                >
                  <Td>
                    <Link
                      href={`/loans/${l.id}`}
                      className="whitespace-nowrap font-mono text-data underline underline-offset-4 hover:no-underline"
                    >
                      {l.loan_code}
                    </Link>
                    <span className="mt-0.5 block whitespace-nowrap text-micro text-ink-faint">
                      {l.member.full_name} · {l.member.member_code}
                    </span>
                  </Td>
                  <Td className="hidden sm:table-cell">
                    {l.next_due_date ? (
                      <>
                        <span className="tnum">{formatDateShort(l.next_due_date)}</span>
                        <span className="mt-0.5 block text-micro text-ink-faint">
                          {relativeDate(l.next_due_date, now)}
                        </span>
                      </>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </Td>
                  <Num>{money(l.outstanding)}</Num>
                  <Td>
                    <StatusBadge status={l.status} />
                  </Td>
                </DisclosureRow>
              );
            })}
            {page.items.length === 0 && <EmptyRow cols={COLS}>No loans match.</EmptyRow>}
          </tbody>
        </Table>
      </div>

      <p className="mt-3 text-micro uppercase text-ink-faint">{page.total} total</p>
    </div>
  );
}
