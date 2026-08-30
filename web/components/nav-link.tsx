"use client";

/**
 * The header had no active-state indication at all. Pathname is only readable on
 * the client, so this is a deliberately tiny client boundary around one link.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`-mb-px border-b-2 py-3.5 text-sm transition-colors duration-150 ${
        active
          ? "border-ink font-medium text-ink"
          : "border-transparent text-ink-muted hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}
