"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "@/app/sign-in/actions";
import { Navigation } from "@/components/navigation";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/sign-in") return children;

  return (
    <>
      <header className="siteHeader">
        <div className="brand">
          <Link href="/" aria-label="LMIO 指挥中心">
            <span>LEON</span>
            <strong>Market Intelligence OS</strong>
          </Link>
          <p>中文优先 · 美股研究与决策支持 · 不执行交易</p>
        </div>
        <div className="headerActions">
          <div className="safety">CAN_TRADE = FALSE</div>
          <form action={signOut}>
            <button className="signOutButton" type="submit">退出</button>
          </form>
        </div>
      </header>
      <Navigation />
      <main>{children}</main>
      <footer>
        <p>Bayview OS 管理项目记忆；LMIO 保存详细市场运行证据。</p>
        <p>研究工具，不构成投资建议，不具备订单执行能力。</p>
      </footer>
    </>
  );
}
