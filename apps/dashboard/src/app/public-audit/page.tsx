import type { Metadata } from "next";
import Link from "next/link";
import { dashboardSections } from "@/lib/navigation";

export const metadata: Metadata = {
  title: "Public Audit View",
  description:
    "Public, read-only audit summary for Leon Market Intelligence OS.",
  robots: { index: false, follow: false },
};

const officialSources = [
  "Federal Reserve official releases",
  "U.S. Bureau of Labor Statistics releases",
  "SEC EDGAR company filings and ownership disclosures",
  "Authorised private Finviz Elite data for internal research only",
];

const auditFacts = [
  ["Purpose", "United States equity research and decision support"],
  ["Operating mode", "Read-only research; no order execution"],
  ["Default language", "Simplified Chinese"],
  ["Trading lock", "CAN_TRADE = FALSE"],
  ["Live trading", "Disabled"],
  ["Paper trading", "Disabled"],
  ["Private data", "Not exposed by this public audit view"],
];

export default function PublicAuditPage() {
  return (
    <main className="publicAudit">
      <header className="publicAuditHero">
        <div>
          <p className="eyebrow">BAYVIEW ENTERPRISE · PUBLIC AUDIT VIEW</p>
          <h1>Leon Market Intelligence OS</h1>
          <p className="publicAuditLead">
            A server-rendered, read-only description of LMIO for independent AI
            and human review. The authenticated operating console and licensed
            market data remain private.
          </p>
        </div>
        <div className="publicAuditLock">NO TRADING · NO PRIVATE DATA</div>
      </header>

      <section aria-labelledby="audit-boundary">
        <p className="eyebrow">AUDIT BOUNDARY</p>
        <h2 id="audit-boundary">What this public page proves</h2>
        <p>
          This page can be fetched without login and its essential content is
          present in the initial HTML response. It describes the product,
          modules, sources and safeguards. It does not expose credentials,
          licensed datasets, watchlists, candidate research, account details or
          internal records.
        </p>
        <dl className="publicAuditFacts">
          {auditFacts.map(([term, detail]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{detail}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="audit-modules">
        <p className="eyebrow">PRODUCT MAP</p>
        <h2 id="audit-modules">13 operating modules</h2>
        <div className="publicAuditGrid">
          {dashboardSections.map((section, index) => (
            <article key={section.slug} id={section.slug}>
              <p className="publicAuditNumber">{String(index + 1).padStart(2, "0")}</p>
              <h3>{section.label}</h3>
              <p className="publicAuditEnglish">{section.eyebrow}</p>
              <p>{section.description}</p>
              <p className="publicAuditStatus">
                {section.deferred
                  ? "Status: deliberately deferred; no fabricated data"
                  : "Status: implemented inside the private console"}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="audit-sources">
        <p className="eyebrow">SOURCE POLICY</p>
        <h2 id="audit-sources">Verified and authorised sources</h2>
        <ul className="publicAuditList">
          {officialSources.map((source) => (
            <li key={source}>{source}</li>
          ))}
        </ul>
        <p>
          Missing evidence remains visibly unavailable. LMIO does not infer a
          live fact from an absent provider and does not present generated text
          as market evidence.
        </p>
      </section>

      <section aria-labelledby="audit-controls">
        <p className="eyebrow">SAFETY CONTROLS</p>
        <h2 id="audit-controls">Fail-closed operating boundaries</h2>
        <ul className="publicAuditList">
          <li>No broker connection or order-execution path.</li>
          <li>No public access to the authenticated dashboard or runtime API.</li>
          <li>Secrets remain server-side and are never returned to the browser.</li>
          <li>Licensed Finviz records are not republished in this public view.</li>
          <li>Research output is decision support, not investment advice.</li>
        </ul>
      </section>

      <footer className="publicAuditFooter">
        <p>
          Public audit view only. Authorised operators may use the private
          console after authentication.
        </p>
        <Link href="/sign-in">Authorised operator sign-in</Link>
      </footer>
    </main>
  );
}
