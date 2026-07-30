import type { Metadata } from "next";
import Link from "next/link";
import { Navigation } from "@/components/navigation";
import "./globals.css";

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
        <header className="siteHeader">
          <div className="brand">
            <Link href="/" aria-label="LMIO 指挥中心">
              <span>LEON</span>
              <strong>Market Intelligence OS</strong>
            </Link>
            <p>中文优先 · 美股研究与决策支持 · 不执行交易</p>
          </div>
          <div className="safety">CAN_TRADE = FALSE</div>
        </header>
        <Navigation />
        <main>{children}</main>
        <footer>
          <p>Bayview OS 管理项目记忆；LMIO 保存详细市场运行证据。</p>
          <p>研究工具，不构成投资建议，不具备订单执行能力。</p>
        </footer>
      </body>
    </html>
  );
}
