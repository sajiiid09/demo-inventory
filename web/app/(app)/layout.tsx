import Link from "next/link";
import { redirect } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/actions";
import type { User } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/members", label: "Members" },
  { href: "/loans", label: "Loans" },
];

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  let user: User;
  try {
    user = await api.get<User>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) redirect("/login");
    throw err;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <span className="font-semibold">MicroLoan</span>
            <nav className="flex gap-4 text-sm">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="text-gray-600 hover:text-gray-900">
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-gray-500">
              {user.full_name} · {user.role}
            </span>
            <form action={logout}>
              <button type="submit" className="text-gray-500 hover:text-gray-900">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
