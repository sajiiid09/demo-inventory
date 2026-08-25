import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MicroLoan Demo",
  description: "A small, deliberately simple loan-management system.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
