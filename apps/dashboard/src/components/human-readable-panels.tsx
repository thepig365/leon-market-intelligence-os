import Link from "next/link";
import type { LMIOResult } from "@/lib/lmio";
import type { DashboardSection } from "@/lib/navigation";
import { TopTenPanel } from "@/components/top-ten-panel";

type UnknownRecord = Record<string, unknown>;

const strategyLabels: Record<string, string> = {
  quality_growth_momentum: "质量成长动量",
  earnings_revision_momentum: "盈利预期改善",
  earnings_revision: "盈利预期改善",
  institutional_accumulation: "机构持续增持",
  activist_catalyst: "积极股东催化",
  insider_value: "内部人价值确认",
  quality_at_reasonable_price: "优质合理估值",
  post_earnings_announcement_drift: "业绩后趋势延续",
  news_driven: "重大新闻变化",
  oversold_reversal: "超卖修复观察",
  short_squeeze: "空头回补观察",
  pattern_recognition: "价格图形识别",
};

const strategyGuide = [
  ["质量成长动量", "寻找盈利质量、增长和价格强度同时改善的公司。"],
  ["盈利预期改善", "观察分析师盈利预测是否持续上调，而不是只看一次好消息。"],
  ["机构持续增持", "确认专业机构持仓变化，但不会仅凭机构买入就入选。"],
  ["积极股东催化", "识别可能推动公司改善资本配置或治理的已披露事件。"],
  ["内部人价值确认", "观察管理层以自有资金买入，并结合估值与基本面核查。"],
  ["优质合理估值", "寻找经营质量较好、价格没有明显透支的公司。"],
  ["业绩后趋势延续", "观察业绩意外后，基本面修正与价格确认是否持续。"],
  ["重大新闻变化", "只使用可核验来源，并等待市场反应确认；新闻不能直接触发交易。"],
  ["超卖修复观察", "寻找过度下跌后的修复条件，避免把下跌本身当成便宜。"],
  ["空头回补观察", "识别高空头仓位与催化剂组合，同时明确失败风险。"],
  ["价格图形识别", "识别底部突破、上升三角、双底和上升趋势回踩，必须等待确认。"],
] as const;

const newsTypeLabels: Record<string, string> = {
  macro_monetary_policy: "美联储与利率",
  macro_employment: "就业报告",
  macro_inflation_cpi: "消费者通胀",
  macro_inflation_ppi: "生产端通胀",
  macro_job_openings: "职位空缺",
  beneficial_ownership: "大股东持仓",
  institutional_holdings: "机构持仓",
  insider_transaction: "内部人士交易",
};

const marketRegimeLabels: Record<string, string> = {
  "Risk-On": "风险偏好",
  "Risk-Off": "风险规避",
  "High Volatility": "高波动",
  "Low Volatility": "低波动",
  "Range": "区间震荡",
  "Macro Shock": "宏观冲击",
};

function newsType(value: unknown) {
  const code = text(value, "other");
  if (newsTypeLabels[code]) return newsTypeLabels[code];
  if (code.startsWith("sec_8-k")) return "公司重大公告";
  if (code.startsWith("sec_10-k")) return "年度业绩申报";
  if (code.startsWith("sec_10-q")) return "季度业绩申报";
  if (code.startsWith("sec_13")) return "机构或大股东持仓";
  if (code.startsWith("sec_4")) return "内部人士交易";
  return "其他已核实事件";
}

function newsPriority(value: unknown) {
  const score = typeof value === "number" ? value : 0;
  if (score >= 90) return "最高关注";
  if (score >= 80) return "重点关注";
  return "持续观察";
}

function record(value: unknown): UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function text(value: unknown, fallback = "待核实") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function number(value: unknown, digits = 0) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-AU", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      })
    : "—";
}

function percent(value: unknown) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value <= 1 ? value * 100 : value)}%`
    : "—";
}

function date(value: unknown) {
  if (typeof value !== "string") return "时间待确认";
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? value
    : parsed.toLocaleString("zh-CN", { timeZone: "Australia/Melbourne" });
}

function payload(value: unknown) {
  const item = record(value);
  return record(item.payload);
}

function resultPayload(value: unknown) {
  const item = record(value);
  return record(item.result_payload);
}

function StatePanel({
  result,
  title,
}: {
  result: LMIOResult;
  title: string;
}) {
  if (result.state === "ready") return null;
  return (
    <section className="panel" aria-live="polite">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">SAFE STATUS</p>
          <h2>{title}</h2>
        </div>
        <span className={`status status-${result.state}`}>
          {result.state === "empty" ? "等待资料" : "暂时不可用"}
        </span>
      </div>
      <p className="message">{result.message}</p>
      <p className="timestamp">最近检查：{date(result.checkedAt)}</p>
    </section>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <section className="panel">
      <p className="eyebrow">NO QUALIFIED RECORDS</p>
      <h2>目前没有可展示的已核实记录</h2>
      <p className="message">{message}</p>
    </section>
  );
}

function CommandCentrePanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") {
    return <StatePanel result={result} title="指挥中心尚未取得运行资料" />;
  }
  const command = record(result.data);
  const regime = record(command.regime);
  const funnel = record(command.funnel);
  const top = list(command.research_queue).map(record);
  const qualified = list(command.qualified_priorities).map(record);
  const events = list(command.important_events).map(record);
  const riskBlocks = list(command.risk_blocks).map((item) => text(item));
  const warnings = list(command.warnings).map((item) => text(item));
  const providers = record(command.provider_health);
  const latestProvider = record(command.latest_provider);
  const telegram = record(command.telegram);
  const safety = record(command.safety);
  const finviz = record(
    providers.finviz_elite_api ??
      providers.finviz_elite_csv ??
      providers.finviz,
  );
  const regimeVerified = text(regime.label, "Unverified") !== "Unverified";
  const regimeLabel = text(regime.label, "Unverified");
  const regimeEvidence = list(regime.evidence).map((item) => text(item));
  const finvizReady = text(finviz.state, "disabled") === "ready";
  const telegramReady =
    telegram.configured === true && telegram.private_queries_configured === true;
  const tradingLocked =
    safety.can_trade === false &&
    safety.live_trading_enabled === false &&
    safety.paper_trading_enabled === false;

  return (
    <section className="researchView">
      <div className="commandMetrics">
        <div><span>已检查股票</span><strong>{number(funnel.universe_checked)}</strong></div>
        <div><span>符合基础范围</span><strong>{number(funnel.investable)}</strong></div>
        <div><span>策略候选</span><strong>{number(funnel.abnormal_candidates)}</strong></div>
        <div><span>今日研究队列</span><strong>{number(top.length)}</strong></div>
        <div><span>完成全部核验</span><strong>{number(qualified.length)}</strong></div>
      </div>

      <div className="commandStatusGrid">
        <article className="commandStatusCard">
          <div className="commandStatusTop">
            <p className="eyebrow">市场环境</p>
            <span className={`status ${regimeVerified ? "status-ready" : "status-empty"}`}>
              {regimeVerified ? "已核实" : "待核实"}
            </span>
          </div>
          <h2>
            {regimeVerified
              ? `${marketRegimeLabels[regimeLabel] ?? regimeLabel} · ${regimeLabel}`
              : "尚未独立核实"}
          </h2>
          <p>
            {regimeVerified
              ? `置信度 ${percent(regime.confidence)} · ${regimeEvidence.slice(0, 5).join(" · ")}`
              : `置信度 ${percent(regime.confidence)}。未核实时不作方向判断。`}
          </p>
        </article>

        <article className="commandStatusCard">
          <div className="commandStatusTop">
            <p className="eyebrow">FINVIZ 数据</p>
            <span className={`status ${finvizReady ? "status-ready" : "status-empty"}`}>
              {finvizReady ? "连接正常" : "需要检查"}
            </span>
          </div>
          <h2>{finvizReady ? "市场扫描已连接" : "当前状态未确认"}</h2>
          <p>
            最近核验：{date(latestProvider.created_at)}。来源：
            {text(latestProvider.provider, "尚无核验记录")}。
          </p>
        </article>

        <article className="commandStatusCard">
          <div className="commandStatusTop">
            <p className="eyebrow">TELEGRAM</p>
            <span className={`status ${telegramReady ? "status-ready" : "status-empty"}`}>
              {telegramReady ? "可查询" : "需要检查"}
            </span>
          </div>
          <h2>{telegramReady ? "私人查询已连接" : "私人查询尚未就绪"}</h2>
          <p>
            已保存 {number(telegram.delivery_records)} 条发送记录。可发送股票代码、
            <code>/status</code> 或 <code>/help</code>。
          </p>
        </article>

        <article className="commandStatusCard">
          <div className="commandStatusTop">
            <p className="eyebrow">安全边界</p>
            <span className={`status ${tradingLocked ? "status-ready" : "status-unavailable"}`}>
              {tradingLocked ? "已锁定" : "立即停止"}
            </span>
          </div>
          <h2>{tradingLocked ? "所有交易功能关闭" : "安全配置异常"}</h2>
          <p>LMIO 仅提供研究与决策支持，不会建立或执行订单。</p>
        </article>
      </div>

      <div className="sectionHeading">
        <div>
          <p className="eyebrow">TODAY’S PRIORITIES</p>
          <h2>今日 Top 3 研究队列</h2>
        </div>
        <p>按现有证据排序；进入队列不代表已完成估值或可以买入。</p>
      </div>
      {top.length ? (
        <div className="compactCardGrid">
          {top.map((candidate, index) => (
            <article className="plainCard" key={`${text(candidate.symbol)}-${index}`}>
              <div className="plainCardHeading">
                <span className="rank">#{index + 1}</span>
                <div>
                  <h3>{text(candidate.symbol, "—")}</h3>
                  <p>{text(candidate.company, "公司名称待确认")}</p>
                </div>
                <strong>{number(candidate.total_score, 1)}</strong>
              </div>
              <p className="pill">{strategyLabels[text(candidate.strategy)] ?? "综合策略候选"}</p>
              <p>{text(candidate.catalyst, "等待补充研究证据。")}</p>
              <div className="nextCheck">
                <strong>下一项确认</strong>
                <span>{text(candidate.next_confirmation, "核对官方披露、估值与价格确认。")}</span>
              </div>
              <Link className="chartLink" href="/top-10">查看完整候选资料 →</Link>
            </article>
          ))}
        </div>
      ) : (
        <EmptyPanel message="系统不会为了填满榜单而降低筛选标准。" />
      )}

      <div className="commandTwoColumn">
        <section className="plainCard">
          <p className="eyebrow">IMPORTANT EVENTS</p>
          <h2>重要事件</h2>
          {events.length ? (
            <ul className="commandList">
              {events.map((event, index) => (
                <li key={`${text(event.headline)}-${index}`}>
                  <strong>{text(event.headline, "事件标题待确认")}</strong>
                  <span>
                    重要度 {number(event.significance)} · 置信度 {percent(event.confidence)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="message">目前没有通过来源与置信度门槛的重要事件。</p>
          )}
          <Link className="chartLink" href="/news-trading">打开新闻研究 →</Link>
        </section>

        <section className="plainCard">
          <p className="eyebrow">RISK BLOCKS</p>
          <h2>风险封锁与警告</h2>
          {riskBlocks.length || warnings.length ? (
            <ul className="commandList warningList">
              {riskBlocks.map((item) => (
                <li key={`block-${item}`}><strong>已封锁：{item}</strong></li>
              ))}
              {warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          ) : (
            <p className="message">目前没有主动封锁；交易功能仍永久关闭。</p>
          )}
          <Link className="chartLink" href="/system-health">查看系统健康 →</Link>
        </section>
      </div>

      <section className="quickActions" aria-label="指挥中心快捷入口">
        <div>
          <p className="eyebrow">QUICK ACTIONS</p>
          <h2>下一步要做什么</h2>
          <p>从同一处进入候选、筛选、证据、报告和系统状态。</p>
        </div>
        <nav>
          <Link href="/top-10">查看 Top 10</Link>
          <Link href="/strategy-screener">运行结果与策略</Link>
          <Link href="/watchlists">观察名单</Link>
          <Link href="/reports-journal">中文报告</Link>
          <Link href="/system-health">连接与安全状态</Link>
        </nav>
      </section>

      <div className="auditFooter">
        <p><strong>数据模式：</strong>{text(command.data_mode, "待核实")}</p>
        <p><strong>报告时间：</strong>{date(command.generated_at)}</p>
        <p><strong>最近检查：</strong>{date(result.checkedAt)}</p>
      </div>
    </section>
  );
}

function StrategyScreenerPanel({ result }: { result: LMIOResult }) {
  const candidates = result.state === "ready" ? list(result.data).map(record) : [];
  const grouped = candidates.reduce<Record<string, UnknownRecord[]>>((acc, item) => {
    const key = text(item.strategy, "other");
    acc[key] = [...(acc[key] ?? []), item];
    return acc;
  }, {});

  return (
    <section className="researchView">
      {result.state !== "ready" ? (
        <StatePanel result={result} title="等待下一次已核实筛选" />
      ) : null}
      <div className="researchNotice">
        <div>
          <p className="eyebrow">SELECTION FRAMEWORK</p>
          <h2>11 套独立策略，统一证据门槛</h2>
          <p>核心判断由盈利修正、经营质量、估值与价格动量共同构成；图形只负责确认时机。</p>
        </div>
        <span className={`status status-${result.state}`}>
          {result.state === "ready" ? `${candidates.length} 个候选` : "等待市场资料"}
        </span>
      </div>

      <div className="strategyGrid">
        {strategyGuide.map(([name, description]) => {
          const code = Object.entries(strategyLabels).find(([, label]) => label === name)?.[0];
          const matches = code ? grouped[code] ?? [] : [];
          return (
            <article className="strategyCard" key={name}>
              <div className="strategyCount">{matches.length}</div>
              <h2>{name}</h2>
              <p>{description}</p>
              {matches.length ? (
                <div className="tickerList">
                  {matches.slice(0, 8).map((item, index) => (
                    <span key={`${text(item.symbol)}-${index}`}>{text(item.symbol, "—")}</span>
                  ))}
                </div>
              ) : (
                <small>
                  {result.state === "ready"
                    ? "本次没有达到门槛的候选"
                    : "等待下一次已核实筛选"}
                </small>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function NewsPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="新闻研究尚未取得资料" />;
  const board = record(result.data);
  const coverage = list(board.coverage).map(record);
  const events = list(board.events).map(record);
  return (
    <>
      <section className="panel">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">OFFICIAL SOURCES ONLY</p>
            <h2>九类官方研究信息</h2>
          </div>
          <span className="status status-ready">只读研究</span>
        </div>
        <p className="message">
          免费官方来源包括美联储、美国劳工统计局和 SEC EDGAR。每条资料在页面内提供
          简明研究摘要、交易观察和投资重点；不再要求跳转到原始来源才能理解事件。
        </p>
      </section>
      <section className="compactCardGrid" aria-label="新闻来源覆盖状态">
        {coverage.map((item) => {
          const available = text(item.status, "waiting_for_verified_release") === "available";
          return (
            <article className="plainCard" key={text(item.code)}>
              <div className="recordCardTop">
                <div>
                  <p className="eyebrow">{text(item.source)}</p>
                  <h2>{text(item.label)}</h2>
                </div>
                <span className={`status status-${available ? "ready" : "empty"}`}>
                  {available ? `${number(item.event_count)} 条` : "等待更新"}
                </span>
              </div>
              <p>{text(item.description)}</p>
              <p className="pageFootnote">
                {available ? `最近发布：${date(item.latest_published_at)}` : "暂未取得已核验事件；不会以假资料填充。"}
              </p>
            </article>
          );
        })}
      </section>
      {!events.length ? <EmptyPanel message="九类来源已经启用，正在等待下一次官方更新。" /> : null}
      <section className="recordList">
      {events.map((event, index) => {
        const eventType = text(event.event_type, "other");
        return (
        <article className="recordCard" key={`${text(event.headline)}-${index}`}>
          <div className="recordCardTop">
            <div>
              <p className="eyebrow">
                {list(event.symbols).map((item) => text(item)).join(" · ") || "整体市场"}
                {" · "}{newsType(eventType)}
              </p>
              <h2>{text(event.headline, "标题待确认")}</h2>
            </div>
            <span className="scoreBadge">{newsPriority(event.significance)}<small>{number(event.significance)} 分</small></span>
          </div>
          <div className="newsResearchSummary">
            <p className="eyebrow">LMIO 研究摘要</p>
            <p>{text(event.summary)}</p>
          </div>
          <dl className="factGrid">
            <div><dt>交易时应观察</dt><dd>{text(event.trading_focus)}</dd></div>
            <div><dt>投资时应观察</dt><dd>{text(event.investing_focus)}</dd></div>
          </dl>
          <p><strong>仍需核实：</strong>{text(event.missing_information)}</p>
          <dl className="factGrid">
            <div><dt>来源</dt><dd>{text(event.source)}</dd></div>
            <div><dt>来源质量</dt><dd>{number(event.source_tier) === "1" ? "一级官方来源" : `第 ${number(event.source_tier)} 级`}</dd></div>
            <div><dt>置信度</dt><dd>{percent(event.confidence)}</dd></div>
            <div><dt>系统动作</dt><dd>{text(event.system_action, "研究与观察，不执行交易")}</dd></div>
          </dl>
          <p className="pageFootnote">发布时间：{date(event.published_at)}</p>
        </article>
        );
      })}
      </section>
    </>
  );
}

function OwnershipPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="持仓资料尚未取得" />;
  const events = list(result.data).map(record);
  if (!events.length) return <EmptyPanel message="尚无已核验的机构或内部人持仓变化。" />;
  return (
    <section className="recordList">
      {events.map((event, index) => {
        const details = payload(event);
        return (
          <article className="recordCard" key={`${text(event.symbol)}-${index}`}>
            <div className="recordCardTop">
              <div><p className="eyebrow">OWNERSHIP CHANGE</p><h2>{text(event.symbol, "—")}</h2></div>
              <span className="status status-ready">{text(event.event_type, "持仓变化")}</span>
            </div>
            <p>{text(details.summary, text(details.description, "已保存版本化持仓证据，等待研究人员复核其意义。"))}</p>
            <p className="pageFootnote">记录时间：{date(event.created_at)}</p>
            {typeof event.source_url === "string" ? (
              <a className="chartLink" href={event.source_url} rel="noreferrer" target="_blank">查看申报来源 ↗</a>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}

function ValuationPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="估值记录尚未取得" />;
  const valuations = list(result.data).map(record);
  if (!valuations.length) return <EmptyPanel message="尚未完成可复现的三视角估值，系统不会给出猜测价格。" />;
  return (
    <section className="recordList">
      {valuations.map((entry, index) => {
        const valuation = resultPayload(entry);
        const perspectives = [
          ["严格自由现金流", record(valuation.strict_fcf)],
          ["正常化所有者收益", record(valuation.normalised_owner_earnings)],
          ["多模型合理价值", record(valuation.multi_model_fair_value)],
        ] as const;
        return (
          <article className="recordCard" key={`${text(entry.symbol)}-${index}`}>
            <div className="recordCardTop">
              <div><p className="eyebrow">THREE-PERSPECTIVE VALUE</p><h2>{text(entry.symbol, "—")}</h2></div>
              <span className="status status-ready">置信度 {percent(valuation.confidence)}</span>
            </div>
            <div className="valuationGrid">
              {perspectives.map(([label, view]) => (
                <section key={label}>
                  <h3>{label}</h3>
                  <dl>
                    <div><dt>保守</dt><dd>${number(view.pessimistic, 2)}</dd></div>
                    <div><dt>基础</dt><dd>${number(view.base, 2)}</dd></div>
                    <div><dt>乐观</dt><dd>${number(view.optimistic, 2)}</dd></div>
                  </dl>
                  {typeof view.warning === "string" ? <p>{view.warning}</p> : null}
                </section>
              ))}
            </div>
            <div className="candidateMeta">
              <span>安全边际：{percent(valuation.safety_margin)}</span>
              <span>{text(valuation.safety_label, "安全边际待判断")}</span>
              <span>模型版本：{text(valuation.calculation_version)}</span>
            </div>
            <p className="pageFootnote">计算时间：{date(valuation.calculated_at ?? entry.created_at)}</p>
          </article>
        );
      })}
    </section>
  );
}

function WatchlistPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="观察名单尚未取得" />;
  const watchlists = list(result.data).map(record);
  if (!watchlists.length) return <EmptyPanel message="目前没有已保存的观察名单。" />;
  return (
    <section className="compactCardGrid">
      {watchlists.map((item, index) => {
        const details = payload(item);
        const symbols = list(details.symbols ?? details.members).map((symbol) =>
          typeof symbol === "string" ? symbol : text(record(symbol).symbol, "—"),
        );
        return (
          <article className="plainCard" key={`${text(item.name)}-${index}`}>
            <p className="eyebrow">WATCHLIST</p>
            <h2>{text(item.name, "未命名观察名单")}</h2>
            <div className="tickerList">
              {symbols.length ? symbols.map((symbol) => <span key={symbol}>{symbol}</span>) : <small>尚未加入股票</small>}
            </div>
            <p className="pageFootnote">建立时间：{date(item.created_at)}</p>
          </article>
        );
      })}
    </section>
  );
}

function PlansPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="条件计划尚未取得" />;
  const plans = list(result.data).map(record);
  if (!plans.length) return <EmptyPanel message="目前没有等待确认的条件计划。LMIO 不会自动创建订单。" />;
  return (
    <section className="recordList">
      {plans.map((plan, index) => {
        const details = payload(plan);
        return (
          <article className="recordCard" key={`${text(plan.symbol)}-${index}`}>
            <div className="recordCardTop">
              <div><p className="eyebrow">CONDITIONAL RESEARCH PLAN</p><h2>{text(plan.symbol, "—")}</h2></div>
              <span className="status status-empty">{text(plan.state, "草稿")}</span>
            </div>
            <dl className="factGrid">
              <div><dt>确认条件</dt><dd>{text(details.confirmation_condition ?? details.confirmation)}</dd></div>
              <div><dt>失效条件</dt><dd>{text(details.invalidation)}</dd></div>
              <div><dt>观察区间</dt><dd>{text(details.entry_zone)}</dd></div>
              <div><dt>风险参考</dt><dd>{text(details.stop_reference)}</dd></div>
            </dl>
            <p className="safetyLine">仅用于研究确认；不会发送或执行订单。</p>
          </article>
        );
      })}
    </section>
  );
}

function ReportsPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="历史报告尚未取得" />;
  const reports = list(result.data).map(record);
  if (!reports.length) return <EmptyPanel message="尚无已完成的版本化日报。" />;
  return (
    <section className="recordList">
      {reports.map((entry, index) => {
        const report = payload(entry);
        const top = list(report.top_10);
        return (
          <article className="recordCard" key={`${text(entry.id)}-${index}`}>
            <div className="recordCardTop">
              <div><p className="eyebrow">DAILY RESEARCH REPORT</p><h2>{date(report.generated_at ?? entry.created_at)}</h2></div>
              <span className="status status-ready">{top.length} 个观察候选</span>
            </div>
            <p>{text(report.message_zh, "本报告保留研究证据与当时的数据状态。")}</p>
            <div className="tickerList">
              {top.slice(0, 10).map((candidate, candidateIndex) => (
                <span key={`${candidateIndex}-${text(record(candidate).symbol)}`}>{text(record(candidate).symbol, "—")}</span>
              ))}
            </div>
          </article>
        );
      })}
    </section>
  );
}

function HealthPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="系统健康状态暂时不可用" />;
  const health = record(result.data);
  const integrations = record(health.integrations);
  const providers = record(health.latest_provider);
  const facts = [
    ["服务状态", text(health.status, "待检查")],
    ["运行环境", text(health.environment)],
    ["数据提供商", text(providers.provider, text(health.provider_status, "尚未连接"))],
    ["提供商状态", text(providers.state, text(health.provider_status, "待检查"))],
    ["执行交易", health.can_trade === true ? "已启用" : "关闭"],
    ["实盘交易", health.live_trading_enabled === true ? "已启用" : "关闭"],
    ["模拟交易", health.paper_trading_enabled === true ? "已启用" : "关闭"],
    ["Telegram 提醒", integrations.telegram === true ? "已连接" : "未连接或待检查"],
  ];
  return (
    <section className="researchView">
      <div className="healthGrid">
        {facts.map(([label, value]) => (
          <article className="healthCard" key={label}>
            <span>{label}</span><strong>{value}</strong>
          </article>
        ))}
      </div>
      <section className="noticeList">
        <h2>安全边界</h2>
        <ul>
          <li>LMIO 只提供市场研究和决策支持。</li>
          <li>新闻、图形或评分都不能单独触发订单。</li>
          <li>缺失或过期的数据会明确标记，不会被演示数据替代。</li>
        </ul>
      </section>
    </section>
  );
}

function SettingsPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready") return <StatePanel result={result} title="设置状态暂时不可用" />;
  const settings = record(result.data);
  const integrations = record(settings.integrations);
  return (
    <section className="researchView">
      <div className="settingsGrid">
        <article className="plainCard">
          <p className="eyebrow">RESEARCH SCOPE</p>
          <h2>研究范围</h2>
          <dl className="factList">
            <div><dt>市场</dt><dd>美国上市普通股</dd></div>
            <div><dt>默认语言</dt><dd>中文</dd></div>
            <div><dt>选股框架</dt><dd>盈利修正 + 质量 + 估值 + 动量</dd></div>
          </dl>
        </article>
        <article className="plainCard">
          <p className="eyebrow">CONNECTED SERVICES</p>
          <h2>连接状态</h2>
          <dl className="factList">
            <div><dt>Telegram</dt><dd>{integrations.telegram === true ? "已连接" : "未连接或待检查"}</dd></div>
            <div><dt>Finviz</dt><dd>{text(settings.provider_status, "待检查")}</dd></div>
            <div><dt>数据存储</dt><dd>{text(settings.store_backend, "受保护存储")}</dd></div>
          </dl>
        </article>
      </div>
      <p className="safetyLine">密钥、密码和访问令牌只保存在服务器端，本页面不会显示。</p>
    </section>
  );
}

function DeferredPanel({ section }: { section: DashboardSection }) {
  return (
    <section className="panel">
      <div className="panelHeader">
        <div><p className="eyebrow">INTENTIONALLY OFF</p><h2>{section.label}保持关闭</h2></div>
        <span className="status status-empty">V1 延后</span>
      </div>
      <p className="message">
        {section.slug === "paper-trades"
          ? "当前不建立模拟订单、不连接券商，也不具备实盘执行能力。完成独立验证和 Leon 批准前，本模块不会开放。"
          : "尚未选择和批准期权数据提供商。系统不会使用猜测、过期或虚构期权数据填充页面。"}
      </p>
    </section>
  );
}

export function HumanReadablePanel({
  section,
  result,
}: {
  section: DashboardSection;
  result: LMIOResult;
}) {
  if (section.deferred) return <DeferredPanel section={section} />;
  switch (section.slug) {
    case "command-centre": return <CommandCentrePanel result={result} />;
    case "top-10": return <TopTenPanel result={result} />;
    case "strategy-screener": return <StrategyScreenerPanel result={result} />;
    case "news-trading": return <NewsPanel result={result} />;
    case "institutional-insider": return <OwnershipPanel result={result} />;
    case "intrinsic-value": return <ValuationPanel result={result} />;
    case "watchlists": return <WatchlistPanel result={result} />;
    case "conditional-plans": return <PlansPanel result={result} />;
    case "reports-journal": return <ReportsPanel result={result} />;
    case "system-health": return <HealthPanel result={result} />;
    case "settings": return <SettingsPanel result={result} />;
    default: return <StatePanel result={result} title="模块状态" />;
  }
}
