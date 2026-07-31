"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/browser";

export function GoogleSignIn() {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function beginGoogleSignIn() {
    setPending(true);
    setError("");
    const supabase = createClient();
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        queryParams: { prompt: "select_account" },
      },
    });

    if (oauthError) {
      setPending(false);
      setError("Google 登录未能启动，请稍后再试。");
    }
  }

  return (
    <div className="googleSignIn">
      <button type="button" onClick={beginGoogleSignIn} disabled={pending}>
        {pending ? "正在打开 Google…" : "使用 Google 登录"}
      </button>
      {error ? <p className="formError">{error}</p> : null}
    </div>
  );
}
