import { statusClass, statusGlyph } from "@/lib/format";
import { Glyph } from "./icons";

/**
 * Monochrome status chip. Tone (fill weight) encodes urgency, the glyph carries
 * the meaning — so the badge survives greyscale and satisfies `color-not-only`.
 */
export function StatusBadge({ status, className = "" }: { status: string; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-micro font-medium uppercase ${statusClass(
        status,
      )} ${className}`}
    >
      <Glyph name={statusGlyph(status)} />
      {status}
    </span>
  );
}
