"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { identityFromClaims } from "@/lib/auth/identity";
import { mutateLMIO } from "@/lib/lmio";
import { createClient } from "@/lib/supabase/server";

async function authorisedOperator() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  const identity = error ? null : identityFromClaims(data?.claims);
  if (!identity || !["owner", "operator"].includes(identity.role)) {
    redirect("/sign-in?error=unauthorized");
  }
  return identity;
}

export async function recordAcceptanceDecision(formData: FormData) {
  const identity = await authorisedOperator();
  const decision = String(formData.get("decision") ?? "");
  const section = String(formData.get("section") ?? "").slice(0, 120);
  const reason = String(formData.get("reason") ?? "").trim().slice(0, 1000);
  const releaseSha = String(formData.get("release_sha") ?? "unrecorded").slice(0, 80);
  if (!section || !["approved", "rejected", "needs_revision"].includes(decision) || !reason) {
    redirect("/acceptance?result=invalid");
  }
  const result = await mutateLMIO("/api/v1/feedback", {
    subject_type: "operator_acceptance",
    subject_id: `${releaseSha}:${section}`,
    decision,
    reason,
    evidence_urls: [],
    verified_identity: identity.id,
    verified_email: identity.email,
    verified_role: identity.role,
  });
  revalidatePath("/acceptance");
  redirect(`/acceptance?result=${result.state === "ready" ? "recorded" : "failed"}`);
}

export async function runAcceptanceControl(formData: FormData) {
  await authorisedOperator();
  const action = String(formData.get("action") ?? "");
  const allowed = new Set([
    "smoke_test",
    "provider_refresh",
    "manual_pipeline",
    "telegram_drain",
    "health_refresh",
    "scheduler_inspect",
    "backup_status",
  ]);
  if (!allowed.has(action)) redirect("/acceptance?result=invalid");
  const result = await mutateLMIO("/api/v1/acceptance/control", { action });
  revalidatePath("/acceptance");
  redirect(`/acceptance?result=${result.state === "ready" ? "control-complete" : "failed"}`);
}
