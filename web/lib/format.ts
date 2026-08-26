/** Money and date formatting — BDT-style 2 decimals, always (API.md §1). */

export function money(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  return n.toLocaleString("en-BD", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-800",
  REJECTED: "bg-gray-200 text-gray-700",
  DISBURSED: "bg-emerald-100 text-emerald-800",
  CLOSED: "bg-gray-100 text-gray-600",
  ACTIVE: "bg-emerald-100 text-emerald-800",
  INACTIVE: "bg-gray-200 text-gray-700",
  PARTIAL: "bg-amber-100 text-amber-800",
  PAID: "bg-emerald-100 text-emerald-800",
};

export function statusClass(status: string): string {
  return STATUS_STYLES[status] ?? "bg-gray-100 text-gray-700";
}
