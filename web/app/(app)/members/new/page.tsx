import Link from "next/link";

import { createMember } from "@/lib/actions";

export default async function NewMemberPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const sp = await searchParams;

  const field = "mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm";

  return (
    <div className="max-w-md">
      <h1 className="text-xl font-semibold">Register member</h1>
      {sp.error && (
        <p className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{sp.error}</p>
      )}
      <form action={createMember} className="mt-4 space-y-3 text-sm">
        <label className="block">
          <span className="text-gray-700">Full name</span>
          <input name="full_name" required className={field} />
        </label>
        <label className="block">
          <span className="text-gray-700">Phone (unique)</span>
          <input name="phone" required className={field} />
        </label>
        <label className="block">
          <span className="text-gray-700">National ID (unique)</span>
          <input name="national_id" required className={field} />
        </label>
        <label className="block">
          <span className="text-gray-700">Address</span>
          <input name="address" className={field} />
        </label>
        <label className="block">
          <span className="text-gray-700">Joined on</span>
          <input name="joined_on" type="date" required defaultValue="2026-01-02" className={field} />
        </label>
        <div className="flex gap-2 pt-2">
          <button className="rounded bg-gray-900 px-3 py-1.5 font-medium text-white hover:bg-gray-700">
            Register
          </button>
          <Link href="/members" className="rounded border border-gray-300 px-3 py-1.5">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
