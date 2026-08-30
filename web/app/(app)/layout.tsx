import { redirect } from "next/navigation";

import { NavLink } from "@/components/nav-link";
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
      {/*
        Wraps to two rows below sm — identity on top, nav beneath — because the
        wordmark, three nav items and the user block do not fit 360px on one line.
      */}
      <header className="border-b border-rule bg-paper">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-8 px-6 sm:flex-nowrap">
          <span className="order-1 py-3 font-mono text-sm font-medium uppercase tracking-[0.18em] sm:py-0">
            MicroLoan
          </span>

          <nav
            aria-label="Main"
            className="order-3 flex w-full gap-6 border-t border-rule sm:order-2 sm:mr-auto sm:w-auto sm:border-t-0"
          >
            {NAV.map((item) => (
              <NavLink key={item.href} href={item.href}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="order-2 flex items-center gap-3 sm:order-3 sm:gap-4">
            <span className="hidden text-sm text-ink-muted md:inline">{user.full_name}</span>
            <span className="border border-rule px-2 py-0.5 text-micro uppercase text-ink-muted">
              {user.role}
            </span>
            <form action={logout}>
              <button
                type="submit"
                className="cursor-pointer text-sm text-ink-muted transition-colors duration-150 hover:text-ink"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
    </div>
  );
}
