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

console.log(
  `Verified ${expected.length} dashboard sections and the protected identity/runtime boundary.`,
);
