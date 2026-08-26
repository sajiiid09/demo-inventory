"use server";

/**
 * Every write goes through here: a server action calls the API with the
 * session cookie, then bounces back with an error banner on failure.
 * One error path for the whole app.
 */

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { api, ApiError } from "@/lib/api";

function fail(path: string, err: unknown): never {
  const message =
    err instanceof ApiError ? err.message : "Something went wrong. Try again.";
  redirect(`${path}?error=${encodeURIComponent(message)}`);
}

export async function createMember(formData: FormData): Promise<void> {
  let id: string | null = null;
  try {
    const member = await api.post<{ id: string }>("/members", {
      full_name: formData.get("full_name"),
      phone: formData.get("phone"),
      national_id: formData.get("national_id"),
      address: formData.get("address") || null,
      joined_on: formData.get("joined_on"),
    });
    id = member.id;
  } catch (err) {
    fail("/members/new", err);
  }
  revalidatePath("/members");
  redirect(`/members?ok=${encodeURIComponent("Member registered.")}`);
}

export async function createLoan(formData: FormData): Promise<void> {
  let loanId: string | null = null;
  try {
    const loan = await api.post<{ id: string }>("/loans", {
      member_id: formData.get("member_id"),
      principal: formData.get("principal"),
      interest_rate_annual: formData.get("interest_rate_annual"),
      term_count: Number(formData.get("term_count")),
      frequency: formData.get("frequency"),
      late_fee: formData.get("late_fee") || "0.00",
      grace_days: Number(formData.get("grace_days") || 3),
      applied_on: formData.get("applied_on"),
    });
    loanId = loan.id;
  } catch (err) {
    fail("/loans/new", err);
  }
  revalidatePath("/loans");
  redirect(`/loans/${loanId}`);
}

export async function approveLoan(formData: FormData): Promise<void> {
  const loanId = String(formData.get("loan_id"));
  try {
    await api.post(`/loans/${loanId}/approve`);
  } catch (err) {
    fail(`/loans/${loanId}`, err);
  }
  revalidatePath(`/loans/${loanId}`);
}

export async function rejectLoan(formData: FormData): Promise<void> {
  const loanId = String(formData.get("loan_id"));
  try {
    await api.post(`/loans/${loanId}/reject`, {
      reason: formData.get("reason"),
    });
  } catch (err) {
    fail(`/loans/${loanId}`, err);
  }
  revalidatePath(`/loans/${loanId}`);
}

export async function disburseLoan(formData: FormData): Promise<void> {
  const loanId = String(formData.get("loan_id"));
  try {
    await api.post(`/loans/${loanId}/disburse`, {
      disbursed_on: formData.get("disbursed_on"),
    });
  } catch (err) {
    fail(`/loans/${loanId}`, err);
  }
  revalidatePath(`/loans/${loanId}`);
}

export async function recordRepayment(formData: FormData): Promise<void> {
  const loanId = String(formData.get("loan_id"));
  try {
    await api.post("/repayments", {
      loan_id: loanId,
      amount: formData.get("amount"),
      paid_on: formData.get("paid_on"),
      method: formData.get("method"),
      note: formData.get("note") || null,
    });
  } catch (err) {
    fail(`/loans/${loanId}`, err);
  }
  revalidatePath(`/loans/${loanId}`);
}

export async function logout(): Promise<void> {
  // No auth check on purpose: calling this action directly clears a cookie and
  // nothing else — it cannot read, change, or sign anything. Harmless by design.
  try {
    await api.post("/auth/logout");
  } finally {
    // Clear the cookie on the web origin too, then go back to the gate.
    (await cookies()).delete("access_token");
    redirect("/login");
  }
}
