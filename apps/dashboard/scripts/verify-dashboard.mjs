import { readFile } from "node:fs/promises";

const navigation = await readFile(
  new URL("../src/lib/navigation.ts", import.meta.url),
  "utf8",
);
const layout = await readFile(new URL("../src/app/layout.tsx", import.meta.url), "utf8");
const appShell = await readFile(
  new URL("../src/components/app-shell.tsx", import.meta.url),
  "utf8",
);
const identity = await readFile(
  new URL("../src/lib/auth/identity.ts", import.meta.url),
  "utf8",
);
const runtime = await readFile(new URL("../src/lib/lmio.ts", import.meta.url), "utf8");
const googleSignIn = await readFile(
  new URL("../src/components/google-sign-in.tsx", import.meta.url),
  "utf8",
);
const authCallback = await readFile(
  new URL("../src/app/auth/callback/route.ts", import.meta.url),
  "utf8",
);
const sectionPage = await readFile(
  new URL("../src/app/[section]/page.tsx", import.meta.url),
  "utf8",
);
const humanReadablePanels = await readFile(
  new URL("../src/components/human-readable-panels.tsx", import.meta.url),
  "utf8",
);
const proxy = await readFile(new URL("../src/proxy.ts", import.meta.url), "utf8");
const publicAudit = await readFile(
  new URL("../src/app/public-audit/page.tsx", import.meta.url),
  "utf8",
);

const expected = [
  "command-centre",
  "top-10",
  "strategy-screener",
  "news-trading",
  "institutional-insider",
  "intrinsic-value",
  "unusual-options",
  "watchlists",
  "conditional-plans",
  "paper-trades",
  "reports-journal",
  "system-health",
  "settings",
];

for (const slug of expected) {
  if (!navigation.includes(`slug: "${slug}"`)) {
    throw new Error(`Missing required dashboard section: ${slug}`);
  }
}

if (!layout.includes("robots: { index: false, follow: false }")) {
  throw new Error("Dashboard must remain excluded from public indexing.");
}
if (!proxy.includes('"/public-audit"')) {
  throw new Error("Public audit page must be accessible without authentication.");
}
if (
  !publicAudit.includes("dashboardSections") ||
  !publicAudit.includes("CAN_TRADE = FALSE") ||
  !publicAudit.includes("NO TRADING · NO PRIVATE DATA")
) {
  throw new Error("Public audit page must document all modules and safety boundaries.");
}
for (const forbidden of ["LMIO_READ_KEY", "SUPABASE_SERVICE_ROLE_KEY", "FINVIZ_API_TOKEN"]) {
  if (publicAudit.includes(forbidden)) {
    throw new Error(`Public audit page must not reference a secret: ${forbidden}`);
  }
}
if (!appShell.includes("不执行交易")) {
  throw new Error("Dashboard must display the no-trading boundary.");
}
for (const claim of ["private_beta_access", 'app.status !== "active"', "owner", "operator", "reviewer"]) {
  if (!identity.includes(claim)) {
    throw new Error(`Missing Bayview identity boundary: ${claim}`);
  }
}
if (!runtime.includes('"x-lmio-read-key": key')) {
  throw new Error("Dashboard must authenticate server-to-server runtime reads.");
}
if (!googleSignIn.includes('provider: "google"') || !googleSignIn.includes("/auth/callback")) {
  throw new Error("Dashboard must offer Google login through the protected auth callback.");
}
if (
  !authCallback.includes("exchangeCodeForSession") ||
  !authCallback.includes("identityFromClaims")
) {
  throw new Error("Google callback must exchange the session and enforce Bayview identity claims.");
}
if (!sectionPage.includes("HumanReadablePanel")) {
  throw new Error("All dashboard sections must use the human-readable presentation layer.");
}
if (
  humanReadablePanels.includes("JSON.stringify") ||
  humanReadablePanels.includes("<pre")
) {
  throw new Error("The daily LMIO interface must not expose raw technical data dumps.");
}
for (const slug of expected) {
  if (
    !["unusual-options", "paper-trades"].includes(slug) &&
    !humanReadablePanels.includes(`case "${slug}"`)
  ) {
    throw new Error(`Missing human-readable presenter for: ${slug}`);
  }
}

console.log(
  `Verified ${expected.length} human-readable dashboard sections and the protected identity/runtime/OAuth boundary.`,
);
