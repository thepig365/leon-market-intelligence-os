"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireIdentity } from "@/lib/auth/require-identity";
import { analyseOptionsScreenshot, mutateLMIO } from "@/lib/lmio";

const maximumCsvBytes = 1_000_000;
const maximumScreenshotBytes = 2_000_000;
const acceptedScreenshotTypes = new Set(["image/png", "image/jpeg", "image/webp"]);

export async function importBarchartCSV(formData: FormData) {
  const identity = await requireIdentity();
  if (!["owner", "operator"].includes(identity.role)) {
    redirect("/unusual-options?options_import=unauthorized");
  }
  const file = formData.get("options_csv");
  if (!(file instanceof File) || !file.name.toLowerCase().endsWith(".csv")) {
    redirect("/unusual-options?options_import=invalid");
  }
  if (file.size < 1 || file.size > maximumCsvBytes) {
    redirect("/unusual-options?options_import=size");
  }
  const result = await mutateLMIO("/api/v1/providers/options/barchart-csv", {
    csv_text: await file.text(),
  });
  revalidatePath("/unusual-options");
  redirect(
    result.state === "ready"
      ? "/unusual-options?options_import=complete"
      : "/unusual-options?options_import=failed",
  );
}

export async function analyseScreenshot(formData: FormData) {
  const identity = await requireIdentity();
  if (identity.role !== "owner" && identity.role !== "operator") {
    redirect("/unusual-options?options_analysis=unauthorized");
  }
  const file = formData.get("options_screenshot");
  if (!(file instanceof File) || !acceptedScreenshotTypes.has(file.type)) {
    redirect("/unusual-options?options_analysis=invalid");
  }
  if (file.size < 1 || file.size > maximumScreenshotBytes) {
    redirect("/unusual-options?options_analysis=size");
  }
  const bytes = Buffer.from(await file.arrayBuffer());
  const dataUrl = `data:${file.type};base64,${bytes.toString("base64")}`;
  const result = await analyseOptionsScreenshot(
    { id: identity.id, role: identity.role as "owner" | "operator" },
    dataUrl,
  );
  revalidatePath("/unusual-options");
  redirect(
    result.state === "ready"
      ? "/unusual-options?options_analysis=complete#screenshot-analysis"
      : "/unusual-options?options_analysis=failed",
  );
}
