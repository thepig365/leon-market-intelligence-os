import { getVercelOidcToken } from "@vercel/oidc";

export type LMIOResult =
  | { state: "ready"; data: unknown; checkedAt: string }
  | { state: "empty"; message: string; checkedAt: string }
  | { state: "unavailable"; message: string; checkedAt: string };

function apiBaseUrl(): string {
  return (process.env.LMIO_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function logRuntimeFailure(context: string, error: unknown): void {
  const message = error instanceof Error ? error.message : "unknown error";
  if (!message.startsWith("Dynamic server usage:")) {
    console.error(context, message);
  }
}

async function runtimeHeaders(): Promise<HeadersInit> {
  const key = process.env.LMIO_READ_API_KEY?.trim();
  let oidcToken = "";
  if (process.env.VERCEL) {
    try {
      oidcToken = await getVercelOidcToken();
    } catch (error) {
      logRuntimeFailure("LMIO OIDC token retrieval failed", error);
      // The runtime read credential remains mandatory. Missing OIDC evidence
      // must fail closed at deployment protection instead of exposing data.
    }
  }
  return {
    Accept: "application/json",
    ...(key ? { "x-lmio-read-key": key } : {}),
    ...(oidcToken ? { "x-vercel-trusted-oidc-idp-token": oidcToken } : {}),
  };
}

export async function readLMIO(endpoint: string | null): Promise<LMIOResult> {
  const checkedAt = new Date().toISOString();
  if (!endpoint) {
    return {
      state: "empty",
      message: "此模块按 V1 决定保持关闭，不会生成模拟的提供商数据。",
      checkedAt,
    };
  }

  try {
    const response = await fetch(`${apiBaseUrl()}${endpoint}`, {
      cache: "no-store",
      headers: await runtimeHeaders(),
      signal: AbortSignal.timeout(20_000),
    });
    if (response.status === 404) {
      return {
        state: "empty",
        message: "尚无已验证运行记录。系统不会用演示数据冒充实时数据。",
        checkedAt,
      };
    }
    if (!response.ok) {
      console.error("LMIO runtime request returned a non-success status", response.status);
      return {
        state: "unavailable",
        message: `LMIO API 返回 ${response.status}；已安全降级。`,
        checkedAt,
      };
    }
    return { state: "ready", data: await response.json(), checkedAt };
  } catch (error) {
    logRuntimeFailure("LMIO runtime request failed", error);
    return {
      state: "unavailable",
      message: "LMIO API 当前不可访问。没有数据被替代或虚构。",
      checkedAt,
    };
  }
}

export async function mutateLMIO(
  endpoint: string,
  body: Record<string, unknown>,
): Promise<LMIOResult> {
  const checkedAt = new Date().toISOString();
  const adminKey = process.env.LMIO_ADMIN_API_KEY?.trim();
  if (!adminKey) {
    return {
      state: "unavailable",
      message: "受保护操作尚未配置；没有任何资料被更改。",
      checkedAt,
    };
  }
  try {
    const response = await fetch(`${apiBaseUrl()}${endpoint}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        ...(await runtimeHeaders()),
        "Content-Type": "application/json",
        "x-lmio-key": adminKey,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      return {
        state: "unavailable",
        message: `受保护操作未完成（${response.status}）；旧资料保持不变。`,
        checkedAt,
      };
    }
    return { state: "ready", data: await response.json(), checkedAt };
  } catch {
    return {
      state: "unavailable",
      message: "运行服务当前不可访问；旧资料保持不变。",
      checkedAt,
    };
  }
}
