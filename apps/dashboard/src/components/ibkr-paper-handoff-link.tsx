"use client";

import { useState } from "react";

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

  function launchTraderWorkstation() {
    void copyTicker().then((didCopy) => {
      if (didCopy) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2500);
      }
    });
  }

  const traderWorkstationUrl = `lmio-tws://open?symbol=${encodeURIComponent(symbol)}`;

  return (
    <a
      aria-label={`复制 ${symbol} 并打开 Trader Workstation Paper Trading 登录`}
      className="tickerHandoff"
      href={traderWorkstationUrl}
      onClick={launchTraderWorkstation}
      title="复制代码并打开 Trader Workstation；请使用 Paper Trading 账户登录"
    >
      {symbol} ↗
      <span className="srOnly" aria-live="polite">
        {copied ? `${symbol} 已复制` : ""}
      </span>
    </a>
  );
}
