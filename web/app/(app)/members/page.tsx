import Link from "next/link";

import { DisclosureRow } from "@/components/ui/disclosure-row";
import { DetailItem } from "@/components/ui/detail";
import { Search } from "@/components/ui/icons";
import { StatusBadge } from "@/components/ui/status";
import { EmptyRow, Num, Table, Td, Th } from "@/components/ui/table";
import { buttonClass } from "@/components/ui/button";
import { fieldClass } from "@/components/ui/field";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { MemberListItem, Page } from "@/lib/types";

const COLS = 4;

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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-medium tracking-tight">Members</h1>
        <Link href="/members/new" className={buttonClass("primary")}>
          Register member
        </Link>
      </div>

      <form className="mt-6 flex gap-2" action="/members">
        <div className="relative w-full max-w-sm">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint">
            <Search />
          </span>
          <input
            name="q"
            defaultValue={sp.q ?? ""}
            aria-label="Search members"
            placeholder="Search name, phone, or member code…"
            className={`${fieldClass} mt-0 pl-9`}
          />
        </div>
        <button className={buttonClass("secondary")}>Search</button>
      </form>

      {sp.ok && (
        <p className="mt-4 border-l-2 border-ink bg-paper-muted px-3 py-2 text-sm">{sp.ok}</p>
      )}
      {sp.error && (
        <p className="mt-4 border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
          {sp.error}
        </p>
      )}

      <div className="mt-6">
        <Table className="min-w-[28rem]">
          <thead>
            <tr>
              <Th>Member</Th>
              <Th>Status</Th>
              <Th align="right">Outstanding</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {page.items.map((m) => (
              <DisclosureRow
                key={m.id}
                cols={COLS}
                label={`member ${m.member_code}`}
                detail={
                  <dl className="grid max-w-2xl gap-x-10 sm:grid-cols-2">
                    <DetailItem label="Phone" value={m.phone} />
                    <DetailItem
                      label="Active loan"
                      value={
                        m.active_loan_code ? (
                          <Link
                            href={`/loans?q=${m.active_loan_code}`}
                            className="font-mono underline underline-offset-4 hover:no-underline"
                          >
                            {m.active_loan_code}
                          </Link>
                        ) : (
                          "—"
                        )
                      }
                    />
                    <DetailItem
                      label="All loans"
                      value={
                        <Link
                          href={`/loans?q=${m.member_code}`}
                          className="underline underline-offset-4 hover:no-underline"
                        >
                          View
                        </Link>
                      }
                    />
                  </dl>
                }
              >
                <Td>
                  <span className="whitespace-nowrap text-ink">{m.full_name}</span>
                  <span className="mt-0.5 block whitespace-nowrap font-mono text-micro text-ink-faint">
                    {m.member_code}
                  </span>
                </Td>
                <Td>
                  <StatusBadge status={m.status} />
                </Td>
                <Num>{money(m.outstanding)}</Num>
              </DisclosureRow>
            ))}
            {page.items.length === 0 && <EmptyRow cols={COLS}>No members match.</EmptyRow>}
          </tbody>
        </Table>
      </div>

      <p className="mt-3 text-micro uppercase text-ink-faint">{page.total} total</p>
    </div>
  );
}
