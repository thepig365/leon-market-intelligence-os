export type LMIOResult =
  | { state: "ready"; data: unknown; checkedAt: string }
  | { state: "empty"; message: string; checkedAt: string }
  | { state: "unavailable"; message: string; checkedAt: string };

function apiBaseUrl(): string {
  return (process.env.LMIO_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function runtimeHeaders(): HeadersInit {
  const key = process.env.LMIO_READ_API_KEY?.trim();
  return key
    ? { Accept: "application/json", "x-lmio-read-key": key }
    : { Accept: "application/json" };
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
      headers: runtimeHeaders(),
      signal: AbortSignal.timeout(5_000),
    });
    if (response.status === 404) {
      return {
        state: "empty",
        message: "尚无已验证运行记录。系统不会用演示数据冒充实时数据。",
        checkedAt,
      };
    }
    if (!response.ok) {
      return {
        state: "unavailable",
        message: `LMIO API 返回 ${response.status}；已安全降级。`,
        checkedAt,
      };
    }
    return { state: "ready", data: await response.json(), checkedAt };
  } catch {
    return {
      state: "unavailable",
      message: "LMIO API 当前不可访问。没有数据被替代或虚构。",
      checkedAt,
    };
  }
}
