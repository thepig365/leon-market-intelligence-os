import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

// The authenticated refresh Server Action inherits this route limit. The
// runtime coordinator is bounded and read-only, but its verified production
// run can take just over four minutes when Finviz and official-news sources
// are both refreshed.
export const maxDuration = 300;

export const metadata: Metadata = {
  title: {
    default: "Leon Market Intelligence OS",
    template: "%s · LMIO",
  },
  description: "Evidence-backed United States equity research and decision support.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
