"use client";

import { useState } from "react";

const IBKR_CLIENT_PORTAL_URL =
  "https://www.interactivebrokers.com.au/sso/Login?forwardTo=22";

export function IbkrPaperHandoffLink({ symbol }: { symbol: string }) {
  const [copied, setCopied] = useState(false);

  async function copyTicker() {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(symbol);
        return true;
      }
    } catch {
      // Use the browser-compatible fallback below when clipboard permission is unavailable.
    }

    const field = document.createElement("textarea");
    field.value = symbol;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    const copiedByFallback = document.execCommand("copy");
    field.remove();
    return copiedByFallback;
  }

  function openPaperTrading() {
    window.open(IBKR_CLIENT_PORTAL_URL, "_blank", "noopener,noreferrer");
    void copyTicker().then((didCopy) => {
      if (didCopy) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2500);
      }
    });
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
