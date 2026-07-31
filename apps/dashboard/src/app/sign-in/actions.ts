"use server";

import { redirect } from "next/navigation";
import { identityFromClaims } from "@/lib/auth/identity";
import { hasSupabaseEnvironment } from "@/lib/supabase/env";
import { createClient } from "@/lib/supabase/server";

export async function signIn(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) redirect("/sign-in?error=required");
  if (!hasSupabaseEnvironment()) redirect("/sign-in?error=configuration");

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) redirect("/sign-in?error=invalid_credentials");

  const { data, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !identityFromClaims(data?.claims)) {
    await supabase.auth.signOut();
    redirect("/sign-in?error=unauthorized");
  }
  redirect("/");
}

export async function signOut() {
  if (hasSupabaseEnvironment()) {
    const supabase = await createClient();
    await supabase.auth.signOut();
  }
  redirect("/sign-in");
}
