"use client";

/**
 * An expandable table row.
 *
 * This is the ONLY client boundary the tables need: it owns nothing but the
 * open/closed flag. Both the summary cells and the drawer contents are rendered
 * on the server and passed through as children/props, so no data fetching or
 * formatting crosses the boundary.
 *
 * Real <table> semantics are kept on purpose — this is financial data, and a
 * screen reader needs the column associations that a div grid would throw away.
 */

import { useId, useState } from "react";

import { ChevronRight } from "./icons";

export function DisclosureRow({
  cols,
  label,
  detail,
  children,
}: {
  /** Total columns in the table, including the toggle column this adds. */
  cols: number;
  /** Accessible name for the toggle, e.g. "installment 3". */
  label: string;
  detail: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();

  return (
    <>
      <tr
        className={`border-b border-rule transition-colors duration-150 hover:bg-paper-sunken ${
          open ? "bg-paper-sunken" : ""
        }`}
      >
        {children}
        <td className="w-10 px-3 py-2.5 align-top text-right">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={id}
            // `relative` matters: the sr-only label is absolutely positioned, and without a
            // positioned ancestor its containing block is the page, so it escapes the
            // table's horizontal scroll container and drags the viewport 5px wide.
            className="relative -my-2 -mr-2 inline-flex h-11 w-11 cursor-pointer items-center justify-center text-ink-faint transition-colors duration-150 hover:text-ink"
          >
            <span className="sr-only">
              {open ? "Hide" : "Show"} details for {label}
            </span>
            <ChevronRight
              className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`}
            />
          </button>
        </td>
      </tr>
      <tr id={id} hidden={!open}>
        <td colSpan={cols} className="border-b border-rule bg-paper-sunken px-3 pb-5 pt-1">
          {detail}
        </td>
      </tr>
    </>
  );
}
