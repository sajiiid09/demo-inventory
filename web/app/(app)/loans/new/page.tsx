import { api } from "@/lib/api";
import { LoanForm } from "@/components/loan-form";
import type { MemberListItem, Page } from "@/lib/types";

export default async function NewLoanPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const sp = await searchParams;
  const members = await api.get<Page<MemberListItem>>("/members?page_size=100").catch(() => ({
    items: [],
    total: 0,
    page: 1,
    page_size: 0,
  }));

  return (
    <div>
      <h1 className="text-xl font-semibold">New loan application</h1>
      {sp.error && (
        <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{sp.error}</p>
      )}
      <div className="mt-4">
        <LoanForm members={members.items} />
      </div>
    </div>
  );
}
