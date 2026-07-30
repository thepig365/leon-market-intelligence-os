import { readFile } from "node:fs/promises";

const navigation = await readFile(
  new URL("../src/lib/navigation.ts", import.meta.url),
  "utf8",
);
const layout = await readFile(new URL("../src/app/layout.tsx", import.meta.url), "utf8");

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
if (!layout.includes("不执行交易")) {
  throw new Error("Dashboard must display the no-trading boundary.");
}

console.log(`Verified ${expected.length} required LMIO dashboard sections.`);
