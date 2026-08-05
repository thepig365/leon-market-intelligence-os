"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireIdentity } from "@/lib/auth/require-identity";
import { refreshLMIO } from "@/lib/lmio";

const refreshablePaths = [
  "/",
  "/command-centre",
  "/top-10",
  "/strategy-screener",
  "/news-trading",
  "/institutional-insider",
  "/intrinsic-value",
  "/watchlists",
  "/conditional-plans",
  "/reports-journal",
  "/system-health",
  "/settings",
  "/unusual-options",
  "/paper-trades",
  "/acceptance",
];

function safeReturnPath(value: FormDataEntryValue | null): string {
  const candidate = String(value ?? "/command-centre");
  return refreshablePaths.includes(candidate) ? candidate : "/command-centre";
}

export async function refreshAllResearch(formData: FormData) {
  const identity = await requireIdentity();
  const returnPath = safeReturnPath(formData.get("return_path"));
  if (!["owner", "operator"].includes(identity.role)) {
    redirect(`${returnPath}?refresh=unauthorized`);
  }

  const result = await refreshLMIO({
    id: identity.id,
    role: identity.role as "owner" | "operator",
  });
  for (const path of refreshablePaths) revalidatePath(path);

  if (result.state !== "ready" || !result.data || typeof result.data !== "object") {
    redirect(`${returnPath}?refresh=failed`);
  }
  const status = String((result.data as Record<string, unknown>).status ?? "failed");
  const outcome = status === "succeeded" ? "complete" : status === "partial" ? "partial" : "failed";
  redirect(`${returnPath}?refresh=${outcome}`);
}
