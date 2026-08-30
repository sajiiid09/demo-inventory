"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buttonClass } from "@/components/ui/button";
import { fieldClass } from "@/components/ui/field";
import { apiBaseUrl } from "@/lib/api-url";

const ACCOUNTS = [
  { email: "admin@demo.local", can: "approves and rejects" },
  { email: "officer@demo.local", can: "registers members, creates loans" },
  { email: "cashier@demo.local", can: "disburses, collects" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("officer@demo.local");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // the httpOnly cookie lands on localhost
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail?.message ?? "Login failed.");
      }
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center p-8">
      <p className="font-mono text-micro uppercase tracking-[0.18em] text-ink-muted">
        MicroLoan
      </p>
      <h1 className="mt-3 text-2xl font-medium tracking-tight">Sign in</h1>
      <p className="mt-1 text-sm text-ink-muted">Use one of the demo accounts below.</p>

      <form onSubmit={submit} className="mt-8 space-y-4 border border-rule p-5">
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Email</span>
          <input
            type="text"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={fieldClass}
            required
          />
        </label>
        <label className="block">
          <span className="text-micro uppercase text-ink-muted">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={fieldClass}
            required
          />
        </label>

        {error && (
          <p role="alert" className="border-l-2 border-flag bg-paper-muted px-3 py-2 text-sm text-flag">
            {error}
          </p>
        )}

        <button type="submit" disabled={busy} className={`${buttonClass("primary")} w-full`}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="mt-6 border border-rule">
        {ACCOUNTS.map((a) => (
          <button
            key={a.email}
            type="button"
            onClick={() => {
              setEmail(a.email);
              setPassword("demo1234");
            }}
            className="flex w-full cursor-pointer items-baseline justify-between gap-3 border-b border-rule px-3 py-2 text-left transition-colors duration-150 last:border-b-0 hover:bg-paper-muted"
          >
            <span className="font-mono text-xs">{a.email}</span>
            <span className="text-micro text-ink-faint">{a.can}</span>
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-ink-faint">
        Password <span className="font-mono">demo1234</span> · click a row to fill the form
      </p>
    </main>
  );
}
