"use client";

import { useState } from "react";

const IBKR_CLIENT_PORTAL_URL =
  "https://www.interactivebrokers.com.au/sso/Login?forwardTo=22";

export function IbkrPaperHandoffLink({ symbol }: { symbol: string }) {
  const [copied, setCopied] = useState(false);

  function openPaperTrading() {
    window.open(IBKR_CLIENT_PORTAL_URL, "_blank", "noopener,noreferrer");
    if (navigator.clipboard) {
      void navigator.clipboard.writeText(symbol).then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2500);
      });
    }
  }

  return (
    <button
      aria-label={`复制 ${symbol} 并打开 IBKR Paper Trading 登录`}
      className="tickerHandoff"
      onClick={openPaperTrading}
      title="复制代码并打开 IBKR；请使用 Paper Trading 账户登录"
      type="button"
    >
      {symbol} ↗
      <span className="srOnly" aria-live="polite">
        {copied ? `${symbol} 已复制` : ""}
      </span>
    </button>
  );
}
