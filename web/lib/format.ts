/** Money, dates and status encoding — BDT-style 2 decimals, always (API.md §1). */

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  return n.toLocaleString("en-BD", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Every amount crosses the wire as a string. Parse in one place. */
export function num(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  return typeof value === "string" ? parseFloat(value) || 0 : value;
}

// ── Dates ───────────────────────────────────────────────────────────────────
//
// Calendar dates arrive as a bare "YYYY-MM-DD". `new Date("2026-01-05")` parses
// as UTC midnight, so any negative-offset locale renders the PREVIOUS day. These
// are calendar dates, never instants — build them in local time.

export function parseDate(iso: string): Date {
  if (iso.includes("T")) return new Date(iso);
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function midnight(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** "Mon, 05 Jan 2026" */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return parseDate(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** "05 Jan 2026" — for cells too tight for a weekday. */
export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  return parseDate(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * "8 weeks ago" · "in 5 days" · "today".
 *
 * `now` is passed in rather than read from the clock so a Server Component and
 * the client it hands off to always agree — otherwise the relative string is a
 * hydration mismatch waiting to happen.
 */
export function relativeDate(iso: string | null | undefined, now: Date): string {
  if (!iso) return "";
  const days = Math.round((midnight(parseDate(iso)) - midnight(now)) / 86_400_000);
  if (days === 0) return "today";

  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const abs = Math.abs(days);
  if (abs < 7) return rtf.format(days, "day");
  if (abs < 45) return rtf.format(Math.round(days / 7), "week");
  if (abs < 365) return rtf.format(Math.round(days / 30), "month");
  return rtf.format(Math.round(days / 365), "year");
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * OVERDUE is derived, not an API status. `accrued_fee` is computed server-side
 * as-of today, which makes it the more trustworthy half of the test; the date
 * comparison catches installments still inside their grace window.
 */
export function isOverdue(
  row: { due_date: string; status: string; accrued_fee: string },
  now: Date,
): boolean {
  if (row.status === "PAID") return false;
  if (num(row.accrued_fee) > 0) return true;
  return midnight(parseDate(row.due_date)) < midnight(now);
}

// ── Status encoding ─────────────────────────────────────────────────────────
//
// Strictly monochrome. Fill weight encodes urgency; a glyph carries the meaning
// so nothing depends on colour alone. `flag` is the one chromatic value in the
// system and means overdue or destructive — nothing else.

export type StatusTone = "live" | "await" | "inert" | "flag";
export type GlyphName = "dot" | "half" | "ring" | "check" | "cross" | "square" | "bang";

const TONE: Record<string, StatusTone> = {
  DISBURSED: "live",
  ACTIVE: "live",
  PAID: "live",
  APPROVED: "await",
  PARTIAL: "await",
  PENDING: "inert",
  CLOSED: "inert",
  INACTIVE: "inert",
  REJECTED: "flag",
  OVERDUE: "flag",
};

const GLYPH: Record<string, GlyphName> = {
  DISBURSED: "dot",
  ACTIVE: "dot",
  PAID: "check",
  APPROVED: "check",
  PARTIAL: "half",
  PENDING: "ring",
  CLOSED: "square",
  INACTIVE: "ring",
  REJECTED: "cross",
  OVERDUE: "bang",
};

export const TONE_CLASS: Record<StatusTone, string> = {
  live: "border border-ink bg-ink text-paper",
  await: "border border-ink bg-paper text-ink",
  inert: "border border-rule bg-paper text-ink-muted",
  flag: "border border-flag bg-paper text-flag",
};

export function statusTone(status: string): StatusTone {
  return TONE[status] ?? "inert";
}

export function statusGlyph(status: string): GlyphName {
  return GLYPH[status] ?? "ring";
}

export function statusClass(status: string): string {
  return TONE_CLASS[statusTone(status)];
}
