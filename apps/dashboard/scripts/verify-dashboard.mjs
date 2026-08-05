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
const home = await readFile(new URL("../src/app/page.tsx", import.meta.url), "utf8");
const acceptance = await readFile(
  new URL("../src/app/acceptance/page.tsx", import.meta.url),
  "utf8",
);
const acceptanceActions = await readFile(
  new URL("../src/app/acceptance/actions.ts", import.meta.url),
  "utf8",
);
const refreshActions = await readFile(
  new URL("../src/app/refresh/actions.ts", import.meta.url),
  "utf8",
);
const refreshControl = await readFile(
  new URL("../src/components/refresh-control.tsx", import.meta.url),
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
if (!home.includes('readLMIO("/api/v1/command-centre")') || !home.includes("syntheticWatermark")) {
  throw new Error("Home must use the operating command-centre and watermark non-production data.");
}
if (!publicAudit.includes("fixture-tested") || publicAudit.includes("implemented inside the private console")) {
  throw new Error("Public audit status must separate implementation from live verification.");
}
for (const forbidden of ["LMIO_READ_KEY", "SUPABASE_SERVICE_ROLE_KEY", "FINVIZ_API_TOKEN"]) {
  if (publicAudit.includes(forbidden)) {
    throw new Error(`Public audit page must not reference a secret: ${forbidden}`);
  }
}
if (!appShell.includes("不执行交易")) {
  throw new Error("Dashboard must display the no-trading boundary.");
}
if (!appShell.includes("RefreshControl") || !refreshControl.includes("刷新全部资料")) {
  throw new Error("Authenticated pages must expose the full research refresh control.");
}
for (const required of ["requireIdentity", "owner", "operator", "refreshLMIO", "revalidatePath"]) {
  if (!refreshActions.includes(required)) {
    throw new Error(`Full refresh must retain its server-side identity boundary: ${required}`);
  }
}
if (!runtime.includes("/api/v1/operator/full-refresh") || !runtime.includes("240_000")) {
  throw new Error("Full refresh must use the bounded server-to-server runtime endpoint.");
}
for (const required of [
  "/api/v1/acceptance",
  "六级证据",
  "21-STAGE INSPECTOR",
  "operator_acceptance",
  "模拟或测试资料",
]) {
  if (!acceptance.includes(required) && !acceptanceActions.includes(required)) {
    throw new Error(`Missing protected operator acceptance control: ${required}`);
  }
}
if (!acceptanceActions.includes("authorisedOperator") || !acceptanceActions.includes("mutateLMIO")) {
  throw new Error("Acceptance mutations must enforce identity and remain server-side.");
}
for (const claim of ["private_beta_access", 'app.status !== "active"', "owner", "operator", "reviewer"]) {
  if (!identity.includes(claim)) {
    throw new Error(`Missing Bayview identity boundary: ${claim}`);
  }
}
if (!runtime.includes('"x-lmio-read-key": key')) {
  throw new Error("Dashboard must authenticate server-to-server runtime reads.");
}
if (
  !runtime.includes("getVercelOidcToken") ||
  !runtime.includes('"x-vercel-trusted-oidc-idp-token": oidcToken')
) {
  throw new Error("Protected runtime reads must use Vercel short-lived OIDC trust.");
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
if (!navigation.includes('endpoint: "/api/v1/news/research-board"')) {
  throw new Error("News research must use the complete official-source research board.");
}
for (const required of ["九类官方研究信息", "交易时应观察", "投资时应观察", "仍需核实"]) {
  if (!humanReadablePanels.includes(required)) {
    throw new Error(`Missing human-readable news research field: ${required}`);
  }
}
if (humanReadablePanels.includes("查看原始来源")) {
  throw new Error("News research must be understandable without a source-link handoff.");
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
