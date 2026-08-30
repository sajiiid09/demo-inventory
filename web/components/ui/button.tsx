/**
 * Button classes as a plain function — no cva, clsx or tailwind-merge
 * (ADR-017, amended: zero dependencies).
 *
 * `danger` is the only variant that may use the accent, and it is reserved for
 * genuinely destructive actions so it stays meaningful.
 */
export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const BASE =
  "inline-flex items-center justify-center gap-1.5 border px-3 py-1.5 text-sm font-medium " +
  "transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40";

const VARIANT: Record<ButtonVariant, string> = {
  primary: "on-ink border-ink bg-ink text-paper hover:bg-ink-muted",
  secondary: "border-rule bg-paper text-ink hover:bg-paper-muted hover:border-ink",
  danger: "border-flag bg-paper text-flag hover:bg-flag hover:text-paper",
  ghost: "border-transparent bg-transparent text-ink-muted hover:text-ink",
};

export function buttonClass(variant: ButtonVariant = "primary", extra = ""): string {
  return `${BASE} ${VARIANT[variant]} ${extra}`.trim();
}
