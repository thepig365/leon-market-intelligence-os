"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { signOut } from "@/app/sign-in/actions";
import { Navigation } from "@/components/navigation";
import { RefreshControl } from "@/components/refresh-control";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/sign-in" || pathname === "/public-audit") return children;

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
          <Suspense fallback={<span className="refreshLoading">刷新资料</span>}>
            <RefreshControl returnPath={pathname} />
          </Suspense>
          <div className="safety">CAN_TRADE = FALSE</div>
          <form action={signOut}>
            <button className="signOutButton" type="submit">退出</button>
          </form>
        </div>
      </header>
      <Navigation />
      <main>{children}</main>
      <footer>
        <p>Bayview OS 管理项目记忆；LMIO 保留可复核的研究依据。</p>
        <p>研究工具，不构成投资建议，不具备订单执行能力。</p>
      </footer>
    </>
  );
}
