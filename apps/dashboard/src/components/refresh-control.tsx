"use client";

import { useFormStatus } from "react-dom";
import { useSearchParams } from "next/navigation";
import { refreshAllResearch } from "@/app/refresh/actions";

function RefreshButton() {
  const { pending } = useFormStatus();
  return (
    <button className="refreshButton" disabled={pending} type="submit">
      {pending ? "正在刷新全部资料…" : "刷新全部资料"}
    </button>
  );
}

const messages: Record<string, string> = {
  complete: "全部已连接资料已更新。",
  partial: "可用资料已更新；部分来源暂时不可用，请查看系统健康。",
  failed: "刷新未完成；旧资料保持不变。",
  unauthorized: "当前账号只有查看权限，不能发起刷新。",
};

export function RefreshControl({ returnPath }: { returnPath: string }) {
  const result = useSearchParams().get("refresh") ?? "";
  return (
    <div className="refreshControl">
      <form action={refreshAllResearch}>
        <input name="return_path" type="hidden" value={returnPath} />
        <RefreshButton />
      </form>
      {messages[result] ? (
        <p className={`refreshMessage refreshMessage-${result}`} role="status">
          {messages[result]}
        </p>
      ) : null}
    </div>
  );
}
