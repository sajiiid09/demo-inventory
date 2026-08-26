/**
 * The single typed fetch wrapper — the ONLY place that knows the API URL,
 * forwards the session cookie, and normalises errors (ARCHITECTURE.md §6).
 * Server-side only (Server Components and Server Actions).
 */

import { cookies } from "next/headers";

const API = process.env.API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

type Options = { method?: string; body?: unknown };

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const jar = await cookies();
  const token = jar.get("access_token")?.value;
  const res = await fetch(`${API}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Cookie: `access_token=${token}` } : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    if (detail?.code) {
      throw new ApiError(detail.code, detail.message ?? "Request failed.", res.status);
    }
    throw new ApiError("HTTP_ERROR", `Request failed (${res.status}).`, res.status);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
};

