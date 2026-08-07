import { Suspense } from "react";
import { notFound } from "next/navigation";
import { HumanReadablePanel } from "@/components/human-readable-panels";
import { OptionsImportControl } from "@/components/options-import-control";
import { OptionsScreenshotAnalysisControl } from "@/components/options-screenshot-analysis-control";
import { dashboardSections, sectionBySlug } from "@/lib/navigation";
import { readLMIO } from "@/lib/lmio";

export function generateStaticParams() {
  return dashboardSections.map((section) => ({ section: section.slug }));
}

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section: slug } = await params;
  const section = sectionBySlug(slug);
  if (!section) {
    notFound();
  }
  const result = await readLMIO(section.endpoint);

  return (
    <>
      <section className="hero compact">
        <p className="eyebrow">{section.eyebrow}</p>
        <h1>{section.label}</h1>
        <p className="lede">{section.description}</p>
        {section.deferred ? (
          <p className="deferredNotice">
            此模块不在 V1 激活范围内。没有提供商、模拟内容或交易能力被启用。
          </p>
        ) : null}
      </section>
      <HumanReadablePanel section={section} result={result} />
      {slug === "unusual-options" ? (
        <Suspense fallback={null}>
          <OptionsScreenshotAnalysisControl />
          <OptionsImportControl />
        </Suspense>
      ) : null}
    </>
  );
}
