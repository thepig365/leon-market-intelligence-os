import { redirect } from "next/navigation";
import { identityFromClaims } from "./identity";
import { hasSupabaseEnvironment } from "../supabase/env";
import { createClient } from "../supabase/server";

export async function requireIdentity() {
  if (!hasSupabaseEnvironment()) redirect("/sign-in?error=configuration");
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  const identity = error ? null : identityFromClaims(data?.claims);
  if (!identity) redirect("/sign-in");
  return identity;
}
