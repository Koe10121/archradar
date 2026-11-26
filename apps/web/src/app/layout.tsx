import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArchRadar — Living Architecture Mapper & PR Blast-Radius Radar",
  description:
    "Deterministic Tree-sitter dependency graphs and grounded AI pull request blast-radius analysis.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.JSX.Element {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
