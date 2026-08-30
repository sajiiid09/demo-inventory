import type { Config } from "tailwindcss";

/**
 * Swiss Modernism over Minimalist Monochrome (ADR-017, amended).
 *
 * Two rules the whole system rests on:
 *   1. Zero border-radius, everywhere. `borderRadius` is overridden as a TOP-LEVEL key
 *      rather than extended, so every stock utility — `rounded`, `rounded-lg`,
 *      `rounded-full` — collapses to 0. Rounding cannot creep back in.
 *   2. One chromatic value in the entire palette: `flag`. It means overdue or
 *      destructive and nothing else. Depth comes from border *weight*, not colour
 *      and not shadow.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    borderRadius: {
      none: "0",
      sm: "0",
      DEFAULT: "0",
      md: "0",
      lg: "0",
      xl: "0",
      "2xl": "0",
      "3xl": "0",
      full: "0",
    },
    extend: {
      colors: {
        // Not pure #000 — reads as black, less glare over a dense table. 20:1 on white.
        ink: { DEFAULT: "#0A0A0A", muted: "#525252", faint: "#8A8A8A" },
        paper: { DEFAULT: "#FFFFFF", muted: "#F7F7F7", sunken: "#FAFAFA" },
        rule: { DEFAULT: "#E5E5E5", strong: "#0A0A0A" },
        flag: "#B91C1C",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        micro: ["11px", { lineHeight: "16px", letterSpacing: "0.08em" }],
        data: ["13px", { lineHeight: "18px" }],
        figure: ["28px", { lineHeight: "32px", letterSpacing: "-0.02em" }],
      },
    },
  },
  plugins: [],
};

export default config;
