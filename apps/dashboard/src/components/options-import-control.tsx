"use client";

import { useFormStatus } from "react-dom";
import { useSearchParams } from "next/navigation";
import { importBarchartCSV } from "@/app/options/actions";

const messages: Record<string, string> = {
  complete: "CSV 已安全导入。达到门槛的记录会进入两次确认流程。",
  failed: "导入未完成；原有资料保持不变。",
  invalid: "请选择 Barchart 下载的 CSV 文件。",
  size: "文件必须小于 1 MB。",
  unauthorized: "当前账号没有导入权限。",
};

function ImportButton() {
  const { pending } = useFormStatus();
  return (
    <button className="secondaryButton" disabled={pending} type="submit">
      {pending ? "正在检查并导入…" : "导入 Barchart CSV"}
    </button>
  );
}

export function OptionsImportControl() {
  const result = useSearchParams().get("options_import") ?? "";
  return (
    <section className="optionsImport" aria-labelledby="options-import-title">
      <div>
        <p className="eyebrow">MANUAL FREE-SOURCE CHECK</p>
        <h2 id="options-import-title">导入人工下载的 Barchart CSV</h2>
        <p>
          LMIO 不会登录、抓取或绕过 Barchart。你可把自己下载的 CSV 上传到这里；
          系统只保留达到研究门槛的合约，并且不会执行订单。
        </p>
      </div>
      <form action={importBarchartCSV}>
        <label htmlFor="options_csv">选择 CSV 文件（最多 1 MB）</label>
        <input accept=".csv,text/csv" id="options_csv" name="options_csv" required type="file" />
        <ImportButton />
      </form>
      {messages[result] ? <p className="refreshMessage" role="status">{messages[result]}</p> : null}
    </section>
  );
}
