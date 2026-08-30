import { LoanForm } from "@/components/loan-form";
import { api } from "@/lib/api";
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
      <h1 className="text-xl font-medium tracking-tight">New loan application</h1>
      <p className="mt-1 text-sm text-ink-muted">
        The preview writes nothing — it is the same arithmetic the API will freeze at
        disbursement (ADR-003).
      </p>

      {sp.error && (
        <p className="mt-4 border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
          {sp.error}
        </p>
      )}

      <div className="mt-6">
        <LoanForm members={members.items} />
      </div>
    </div>
  );
}
