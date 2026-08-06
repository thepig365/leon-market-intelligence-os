import Link from "next/link";
import { HumanReadablePanel } from "@/components/human-readable-panels";
import { readLMIO } from "@/lib/lmio";
import { dashboardSections, sectionBySlug } from "@/lib/navigation";

export default async function Home() {
  const command = await readLMIO("/api/v1/command-centre");
  const commandCentre = sectionBySlug("command-centre");
  const payload = command.state === "ready" && typeof command.data === "object" && command.data
    ? command.data as Record<string, unknown>
    : {};
  const dataMode = typeof payload.data_mode === "string" ? payload.data_mode : "unavailable";
  const nonOperational = !["authorised_finviz_api", "operational"].includes(dataMode);

  return (
    <>
      <section className="hero">
        <p className="eyebrow">COMMAND CENTRE</p>
        <h1>把证据变成可审计的投资判断。</h1>
        <p className="lede">
          LMIO 扫描美股、核验变化、分离质量、价值、机会与时机，
          只在证据足够时提醒 Leon。
        </p>
        <div className="guardrails">
          <span>不强迫推荐</span>
          <span>不虚构缺失数据</span>
          <span>不执行交易</span>
        </div>
        {nonOperational ? (
          <p className="syntheticWatermark" role="status">
            非生产资料 · {dataMode} · 不得用于投资决定
          </p>
        ) : null}
      </section>

      <section className="sectionGrid" aria-label="LMIO 功能">
        {dashboardSections.map((section) => (
          <Link className="sectionCard" href={`/${section.slug}`} key={section.slug}>
            <p className="eyebrow">{section.eyebrow}</p>
            <h2>{section.label}</h2>
            <p>{section.description}</p>
            <span>{section.deferred ? "查看安全边界" : "打开模块"} →</span>
          </Link>
        ))}
      </section>

      {commandCentre ? (
        <HumanReadablePanel section={commandCentre} result={command} />
      ) : null}
    </>
  );
}
