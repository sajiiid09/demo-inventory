"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

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
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include", // the httpOnly cookie lands on localhost
          body: JSON.stringify({ email, password }),
        },
      );
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
      <h1 className="text-2xl font-semibold">MicroLoan Demo</h1>
      <p className="mt-1 text-sm text-gray-500">Sign in with a demo account.</p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block text-sm">
          <span className="text-gray-700">Email</span>
          <input
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            required
          />
        </label>
        <label className="block text-sm">
          <span className="text-gray-700">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
            required
          />
        </label>
        {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-gray-900 px-3 py-2 font-medium text-white hover:bg-gray-700 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="mt-6 space-y-1 text-xs text-gray-500">
        <p>admin@demo.local · approves and rejects</p>
        <p>officer@demo.local · registers members, creates loans</p>
        <p>cashier@demo.local · disburses, collects</p>
        <p>(password: demo1234)</p>
      </div>
    </main>
  );
}
