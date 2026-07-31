import { signIn } from "./actions";
import { GoogleSignIn } from "@/components/google-sign-in";

const errors: Record<string, string> = {
  configuration: "LMIO 登录服务尚未完成配置。",
  invalid_credentials: "邮箱或密码不正确。",
  oauth: "Google 登录未完成，请重新尝试。",
  required: "请输入邮箱和密码。",
  unauthorized: "此账号未获 Bayview OS 授权。",
};

export default async function SignIn({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return (
    <main className="signInPage">
      <section className="signInCard">
        <p className="eyebrow">BAYVIEW ENTERPRISE · PRIVATE ACCESS</p>
        <h1>登录 LMIO</h1>
        <p>使用已获授权的 Bayview OS 账号进入市场研究与决策支持系统。</p>
        {error ? <p className="formError">{errors[error] || "登录未完成。"}</p> : null}
        <GoogleSignIn />
        <div className="signInDivider"><span>或使用应用密码</span></div>
        <form action={signIn} className="signInForm">
          <label>
            邮箱
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            密码
            <input name="password" type="password" autoComplete="current-password" required />
          </label>
          <button type="submit">登录</button>
        </form>
        <p className="signInNote">
          LMIO 不接收或保存您的 Google 或应用密码；身份由 Bayview OS 的 Supabase 登录系统验证。
        </p>
      </section>
    </main>
  );
}
