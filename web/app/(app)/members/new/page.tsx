import Link from "next/link";

import { buttonClass } from "@/components/ui/button";
import { fieldClass } from "@/components/ui/field";
import { createMember } from "@/lib/actions";

export default async function NewMemberPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const sp = await searchParams;

  return (
    <div className="max-w-md">
      <h1 className="text-xl font-medium tracking-tight">Register member</h1>
      <p className="mt-1 text-sm text-ink-muted">Phone and national ID must be unique.</p>

      {sp.error && (
        <p className="mt-4 border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
          {sp.error}
        </p>
      )}

      <form action={createMember} className="mt-6 space-y-4 border border-rule p-5">
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Full name</span>
          <input name="full_name" required className={fieldClass} />
        </label>
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Phone</span>
          <input name="phone" required className={fieldClass} />
        </label>
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">National ID</span>
          <input name="national_id" required className={fieldClass} />
        </label>
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Address</span>
          <input name="address" className={fieldClass} />
        </label>
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Joined on</span>
          <input name="joined_on" type="date" required defaultValue="2026-01-02" className={fieldClass} />
        </label>

        <div className="flex gap-2 border-t border-rule pt-4">
          <button className={buttonClass("primary")}>Register</button>
          <Link href="/members" className={buttonClass("secondary")}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
