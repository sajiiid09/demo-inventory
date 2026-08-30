/**
 * The input class string used to be copy-pasted into three separate files.
 * It lives here now.
 */
export const fieldClass =
  "mt-1 w-full border border-rule bg-paper px-3 py-2 text-sm text-ink " +
  "transition-colors duration-150 placeholder:text-ink-faint hover:border-ink-faint " +
  "focus:border-ink focus:outline-none";

export function Field({
  label,
  hint,
  className = "",
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-micro uppercase text-ink-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-micro text-ink-faint">{hint}</span>}
    </label>
  );
}
