import type { LMIOResult } from "@/lib/lmio";

export function StatusPanel({ result }: { result: LMIOResult }) {
  const label =
    result.state === "ready"
      ? "已连接"
      : result.state === "empty"
        ? "等待数据"
        : "安全降级";

  return (
    <section className="panel" aria-live="polite">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">RUNTIME EVIDENCE</p>
          <h2>运行证据</h2>
        </div>
        <span className={`status status-${result.state}`}>{label}</span>
      </div>
      {result.state === "ready" ? (
        <pre>{JSON.stringify(result.data, null, 2)}</pre>
      ) : (
        <p className="message">{result.message}</p>
      )}
      <p className="timestamp">检查时间：{result.checkedAt}</p>
    </section>
  );
}
