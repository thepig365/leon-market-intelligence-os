"use client";

import { useFormStatus } from "react-dom";
import { useSearchParams } from "next/navigation";
import { analyseScreenshot } from "@/app/options/actions";

const messages: Record<string, string> = {
  complete: "分析已完成。截图未保存；请在上方查看最新白话分析。",
  failed: "分析未完成。可能是服务暂时不可用或本月 AI 上限已达到；截图未保存。",
  invalid: "请选择 PNG、JPG 或 WebP 截图。",
  size: "截图必须小于 2 MB。",
  unauthorized: "当前账号没有分析权限。",
};

function AnalyseButton() {
  const { pending } = useFormStatus();
  return (
    <button className="secondaryButton" disabled={pending} type="submit">
      {pending ? "正在读取并分析…" : "AI 分析截图"}
    </button>
  );
}

export function OptionsScreenshotAnalysisControl() {
  const result = useSearchParams().get("options_analysis") ?? "";
  return (
    <section className="optionsImport" aria-labelledby="options-analysis-upload-title">
      <div>
        <p className="eyebrow">PRIVATE AI SCREENSHOT RESEARCH</p>
        <h2 id="options-analysis-upload-title">上传期权异动截图</h2>
        <p>
          LMIO 会提取合约并用中文解释多空线索、风险与需要确认的资料。截图只在本次分析中发送给
          OpenAI，不会保存；结果不会创建订单，也不会把单笔异动当成确定买卖信号。
        </p>
      </div>
      <form action={analyseScreenshot}>
        <label htmlFor="options_screenshot">选择截图（PNG / JPG / WebP，最多 2 MB）</label>
        <input
          accept="image/png,image/jpeg,image/webp"
          id="options_screenshot"
          name="options_screenshot"
          required
          type="file"
        />
        <AnalyseButton />
      </form>
      {messages[result] ? <p className="refreshMessage" role="status">{messages[result]}</p> : null}
    </section>
  );
}
