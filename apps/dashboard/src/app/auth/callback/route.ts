import { NextResponse } from "next/server";
import { identityFromClaims } from "@/lib/auth/identity";
import { hasSupabaseEnvironment } from "@/lib/supabase/env";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const signInUrl = new URL("/sign-in", url.origin);

  if (!hasSupabaseEnvironment()) {
    signInUrl.searchParams.set("error", "configuration");
    return NextResponse.redirect(signInUrl);
  }
  if (!code) {
    signInUrl.searchParams.set("error", "oauth");
    return NextResponse.redirect(signInUrl);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    signInUrl.searchParams.set("error", "oauth");
    return NextResponse.redirect(signInUrl);
  }

  const { data, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !identityFromClaims(data?.claims)) {
    await supabase.auth.signOut();
    signInUrl.searchParams.set("error", "unauthorized");
    return NextResponse.redirect(signInUrl);
  }

  return NextResponse.redirect(new URL("/", url.origin));
}
