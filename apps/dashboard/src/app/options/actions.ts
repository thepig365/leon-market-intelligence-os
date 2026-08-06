"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireIdentity } from "@/lib/auth/require-identity";
import { mutateLMIO } from "@/lib/lmio";

const maximumCsvBytes = 1_000_000;

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
