/**
 * Hand-rolled inline SVGs — no icon dependency (ADR-017, amended).
 *
 * House rules: 16x16 viewBox, 1.5 stroke, square caps to match the zero-radius
 * geometry, `currentColor` throughout so icons inherit the surface they sit on.
 * All are decorative; the adjacent text carries the meaning.
 */

import type { GlyphName } from "@/lib/format";

type IconProps = { size?: number; className?: string };

function svg(size: number, className: string | undefined, children: React.ReactNode) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {children}
    </svg>
  );
}

export function ChevronRight({ size = 12, className }: IconProps) {
  return svg(size, className, <path d="M6 3.5 10.5 8 6 12.5" />);
}

export function Search({ size = 14, className }: IconProps) {
  return svg(
    size,
    className,
    <>
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5 14 14" />
    </>,
  );
}

export function ArrowRight({ size = 12, className }: IconProps) {
  return svg(
    size,
    className,
    <>
      <path d="M2.5 8h11" />
      <path d="M9.5 4 13.5 8l-4 4" />
    </>,
  );
}

/** The status glyphs. Each state gets a distinct shape, not just a distinct fill. */
export function Glyph({ name, size = 10, className }: IconProps & { name: GlyphName }) {
  switch (name) {
    case "dot":
      return svg(size, className, <circle cx="8" cy="8" r="4.5" fill="currentColor" stroke="none" />);
    case "ring":
      return svg(size, className, <circle cx="8" cy="8" r="4.5" />);
    case "half":
      return svg(
        size,
        className,
        <>
          <circle cx="8" cy="8" r="4.5" />
          <path d="M8 3.5a4.5 4.5 0 0 1 0 9z" fill="currentColor" stroke="none" />
        </>,
      );
    case "check":
      return svg(size, className, <path d="M3 8.5 6.5 12 13 4.5" />);
    case "cross":
      return svg(
        size,
        className,
        <>
          <path d="M4 4l8 8" />
          <path d="M12 4l-8 8" />
        </>,
      );
    case "square":
      return svg(size, className, <rect x="3.5" y="3.5" width="9" height="9" fill="currentColor" stroke="none" />);
    case "bang":
      return svg(
        size,
        className,
        <>
          <path d="M8 3v6" />
          <path d="M8 12h.01" strokeWidth={2} />
        </>,
      );
  }
}
