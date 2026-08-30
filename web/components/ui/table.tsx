/**
 * Table primitives. Three near-identical hand-rolled tables used to live in the
 * pages; the markup lives here now.
 *
 * The wrapper scrolls on its own axis so a wide table never makes the page body
 * scroll horizontally.
 */

export function Table({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  // Scroll horizontally only where it is needed. `overflow-x: auto` forces
  // overflow-y to compute as auto too, which creates a scroll container and kills
  // the sticky header — so on md+ the wrapper stays overflow-visible and the
  // header sticks to the viewport instead.
  return (
    <div className="max-md:overflow-x-auto">
      <table className={`w-full border-collapse text-data ${className}`}>{children}</table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
  className = "",
}: {
  children?: React.ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <th
      scope="col"
      className={`sticky top-0 z-10 border-y border-ink bg-paper px-3 py-2 text-micro font-medium uppercase text-ink-muted ${
        align === "right" ? "text-right" : "text-left"
      } ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  className = "",
  ...rest
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={`px-3 py-2.5 align-top ${className}`} {...rest}>
      {children}
    </td>
  );
}

/** Right-aligned, tabular figures — money and counts never reflow. */
export function Num({
  children,
  className = "",
  ...rest
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <Td className={`text-right tnum ${className}`} {...rest}>
      {children}
    </Td>
  );
}

export function EmptyRow({ cols, children }: { cols: number; children: React.ReactNode }) {
  return (
    <tr>
      <td colSpan={cols} className="border-b border-rule px-3 py-12 text-center text-sm text-ink-faint">
        {children}
      </td>
    </tr>
  );
}
