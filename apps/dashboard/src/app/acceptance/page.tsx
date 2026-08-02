import { recordAcceptanceDecision, runAcceptanceControl } from "./actions";
import { readLMIO } from "@/lib/lmio";

type Item = Record<string, unknown>;

const sections = [
  ["A", "产品边界与安全"],
  ["B", "资料来源与新鲜度"],
  ["C", "21 阶段流水线"],
  ["D", "筛选、估值与研究"],
  ["E", "Telegram 与调度"],
  ["F", "故障与恢复"],
  ["G", "前端功能与移动端"],
  ["H", "最终操作员结论"],
] as const;

const controls = [
  ["smoke_test", "运行安全冒烟检查"],
  ["provider_refresh", "刷新授权提供商"],
  ["manual_pipeline", "运行一次研究流水线"],
  ["telegram_drain", "处理 Telegram 待发队列"],
  ["health_refresh", "刷新系统健康"],
  ["scheduler_inspect", "检查调度计划"],
  ["backup_status", "检查备份准备状态"],
] as const;

function record(value: unknown): Item {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Item : {};
}

function list(value: unknown): Item[] {
  return Array.isArray(value) ? value.map(record) : [];
}

function text(value: unknown, fallback = "尚无证据") {
  return typeof value === "string" && value ? value : fallback;
}

function date(value: unknown) {
  if (typeof value !== "string") return "尚无记录";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString("zh-CN", {
    timeZone: "Australia/Melbourne",
  });
}

export default async function AcceptancePage({
  searchParams,
}: {
  searchParams: Promise<{ result?: string }>;
}) {
  const result = await readLMIO("/api/v1/acceptance");
  const query = await searchParams;
  if (result.state !== "ready") {
    return (
      <section className="acceptanceShell">
        <p className="eyebrow">OPERATOR ACCEPTANCE</p>
        <h1>LMIO 验收中心暂时不可用</h1>
        <p>{result.message}</p>
      </section>
    );
  }
  const data = record(result.data);
  const release = record(data.release);
  const readiness = record(data.readiness);
  const pipeline = record(data.pipeline);
  const latestPipeline = record(readiness.latest_pipeline);
  const levels = list(data.evidence_levels);
  const stages = list(pipeline.stages);
  const feedback = list(data.feedback);
  const controlHistory = list(data.control_history);
  const scheduler = record(data.scheduler);
  const jobs = list(scheduler.jobs);
  const blockers = Array.isArray(readiness.blockers) ? readiness.blockers : [];
  const synthetic = data.synthetic_or_fixture === true;

  return (
    <div className="acceptanceShell">
      <section className="acceptanceHero">
        <div>
          <p className="eyebrow">OPERATOR ACCEPTANCE · RC1</p>
          <h1>LMIO v1.0 验收中心</h1>
          <p className="lede">只依据已保存证据判断；代码、配置、真实运行与 Leon 验收互不混淆。</p>
        </div>
        <span className="acceptanceRelease">{text(release.label)}</span>
      </section>

      {query.result ? <p className={`acceptanceNotice result-${query.result}`}>操作结果：{query.result}</p> : null}
      {synthetic ? <p className="syntheticWatermark">模拟或测试资料 · 不得用于投资决定</p> : null}

      <section className="acceptanceFacts">
        <div><span>版本</span><strong>{text(release.version)}</strong></div>
        <div><span>提交</span><strong>{text(release.sha)}</strong></div>
        <div><span>环境</span><strong>{text(release.environment)}</strong></div>
        <div><span>数据库版本</span><strong>{Array.isArray(release.schema_versions) ? release.schema_versions.join(", ") : "—"}</strong></div>
        <div><span>最近流水线</span><strong>{text(latestPipeline.run_id, "尚未运行")}</strong></div>
        <div><span>状态</span><strong>{text(readiness.status)}</strong></div>
      </section>

      <section className="panel">
        <p className="eyebrow">SIX EVIDENCE LEVELS</p>
        <h2>六级证据</h2>
        <div className="evidenceGrid">
          {levels.map((level) => (
            <article key={text(level.level)}>
              <span>{text(level.label)}</span>
              <strong>{text(level.state)}</strong>
              <small>{date(level.checked_at)}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">READINESS BLOCKERS</p>
        <h2>仍需完成的真实证据</h2>
        {blockers.length ? (
          <ul className="acceptanceList">{blockers.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul>
        ) : <p>当前健康资料没有列出阻塞项；仍需 Leon 最终验收。</p>}
      </section>

      <section className="panel">
        <p className="eyebrow">21-STAGE INSPECTOR</p>
        <h2>最近流水线证据</h2>
        <p>要求 21 个阶段；当前保存 {stages.length} 个阶段记录。</p>
        <ol className="stageList">
          {stages.length ? stages.map((stage) => (
            <li key={`${stage.stage_order}-${stage.stage_name}`}>
              <span>{String(stage.stage_order).padStart(2, "0")}</span>
              <strong>{text(stage.stage_name)}</strong>
              <em>{text(stage.status)}</em>
            </li>
          )) : <li className="emptyStage">尚无真实流水线记录。</li>}
        </ol>
      </section>

      <section className="panel">
        <p className="eyebrow">SAFE OPERATOR CONTROLS</p>
        <h2>受保护的安全操作</h2>
        <p>操作由服务器执行，浏览器不会收到任何密钥。所有交易能力保持关闭。</p>
        <div className="controlGrid">
          {controls.map(([action, label]) => (
            <form action={runAcceptanceControl} key={action}>
              <input name="action" type="hidden" value={action} />
              <button type="submit">{label}</button>
            </form>
          ))}
        </div>
        {controlHistory.length ? (
          <ul className="acceptanceList">
            {controlHistory.map((item) => {
              const detail = record(item.payload);
              return (
                <li key={String(item.id)}>
                  <strong>{text(detail.action)} · {text(item.severity)}</strong>
                  <span>{text(detail.actor)} · {date(detail.completed_at)}</span>
                </li>
              );
            })}
          </ul>
        ) : <p>尚无操作记录。</p>}
      </section>

      <section className="panel">
        <p className="eyebrow">SCHEDULER</p>
        <h2>调度状态：{text(scheduler.executor_process)}</h2>
        <div className="schedulerList">
          {jobs.map((job) => (
            <article key={text(job.id)}>
              <strong>{text(job.purpose)}</strong>
              <span>最近：{date(job.last_run)} · {text(job.last_status)}</span>
              <small>下次：{date(job.next_scheduled_time)}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">LEON REVIEW</p>
        <h2>分项确认</h2>
        <div className="acceptanceChecklist">
          {sections.map(([code, label]) => (
            <form action={recordAcceptanceDecision} key={code}>
              <input name="section" type="hidden" value={`${code}-${label}`} />
              <input name="release_sha" type="hidden" value={text(release.sha)} />
              <h3>{code}. {label}</h3>
              <label>
                结论
                <select name="decision" required defaultValue="needs_revision">
                  <option value="approved">批准</option>
                  <option value="needs_revision">需要修正</option>
                  <option value="rejected">拒绝</option>
                </select>
              </label>
              <label>
                说明
                <textarea name="reason" required maxLength={1000} placeholder="写下依据或需要修正的内容" />
              </label>
              <button type="submit">保存这项决定</button>
            </form>
          ))}
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">RECORDED DECISIONS</p>
        <h2>已保存的验收记录</h2>
        {feedback.length ? (
          <ul className="acceptanceList">
            {feedback.map((item) => (
              <li key={String(item.id)}>
                <strong>{text(item.subject_id)} · {text(item.decision)}</strong>
                <span>{text(item.actor)} · {date(item.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : <p>尚无 Leon 验收决定。</p>}
      </section>
    </div>
  );
}
