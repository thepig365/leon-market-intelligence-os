import type { LMIOResult } from "@/lib/lmio";

type Candidate = {
  symbol?: string;
  company?: string;
  strategy?: string;
  market_price?: number;
  total_score?: number;
  catalyst?: string;
  next_confirmation?: string;
  missing_fields?: string[];
  pattern?: {
    name_zh?: string;
    name_en?: string;
    stage?: string;
    key_level?: string;
    volume_confirmation?: string;
    confirmation?: string;
    invalidation?: string;
  };
  scores?: {
    quality?: number;
    valuation?: number;
    timing?: number;
    opportunity?: number;
    confidence?: number;
  };
};

type Report = {
  data_mode?: string;
  generated_at?: string;
  funnel?: {
    universe_checked?: number;
    investable?: number;
    abnormal_candidates?: number;
    watchlist?: number;
    priority_opportunities?: number;
  };
  regime?: {
    label?: string;
    confidence?: number;
    manual_review_required?: boolean;
  };
  top_10?: Candidate[];
  warnings?: string[];
};

const strategyLabels: Record<string, string> = {
  quality_at_reasonable_price: "质量与合理估值",
  short_squeeze: "空头回补观察",
  institutional_accumulation: "机构增持观察",
  earnings_revision: "盈利预期改善",
  quality_growth_momentum: "质量成长动量",
  pattern_recognition: "图形识别",
};

const patternStageLabels: Record<string, string> = {
  forming: "形成中",
  awaiting_confirmation: "等待确认",
  confirmed: "已确认",
  failed: "已失效",
};

function isReport(value: unknown): value is Report {
  return typeof value === "object" && value !== null;
}

function number(value: number | undefined, digits = 0) {
  return typeof value === "number"
    ? value.toLocaleString("en-AU", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      })
    : "待验证";
}

function score(value: number | undefined) {
  return typeof value === "number" ? Math.round(value) : null;
}

export function TopTenPanel({ result }: { result: LMIOResult }) {
  if (result.state !== "ready" || !isReport(result.data)) {
    return (
      <section className="panel" aria-live="polite">
        <div className="panelHeader">
          <div>
            <p className="eyebrow">RESEARCH STATUS</p>
            <h2>研究状态</h2>
          </div>
          <span className={`status status-${result.state}`}>等待数据</span>
        </div>
        <p className="message">
          {result.state === "ready"
            ? "当前报告格式无法读取，系统没有显示未经确认的候选。"
            : result.message}
        </p>
      </section>
    );
  }

  const report = result.data;
  const candidates = Array.isArray(report.top_10) ? report.top_10 : [];
  const funnel = report.funnel ?? {};
  const regimeVerified =
    report.regime?.label && report.regime.label !== "Unverified";

  return (
    <section className="researchView" aria-live="polite">
      <div className="summaryStrip">
        <div>
          <span>已检查</span>
          <strong>{number(funnel.universe_checked)}</strong>
        </div>
        <div>
          <span>符合基础范围</span>
          <strong>{number(funnel.investable)}</strong>
        </div>
        <div>
          <span>策略候选</span>
          <strong>{number(funnel.abnormal_candidates)}</strong>
        </div>
        <div>
          <span>今日观察</span>
          <strong>{number(candidates.length)}</strong>
        </div>
      </div>

      <div className="researchNotice">
        <div>
          <p className="eyebrow">MARKET CHECK</p>
          <h2>{regimeVerified ? report.regime?.label : "市场环境待验证"}</h2>
          <p>
            当前使用 Finviz 授权快照进行初筛。候选仅供进一步研究，不是买入建议。
          </p>
        </div>
        <span className="status status-ready">Finviz 已连接</span>
      </div>

      {candidates.length ? (
        <ol className="candidateGrid">
          {candidates.map((candidate, index) => {
            const symbol = candidate.symbol?.trim();
            const finvizUrl = symbol
              ? `https://elite.finviz.com/quote.ashx?t=${encodeURIComponent(symbol)}`
              : null;
            const candidateScores = [
              ["质量", score(candidate.scores?.quality)],
              ["估值", score(candidate.scores?.valuation)],
              ["时机", score(candidate.scores?.timing)],
              ["机会", score(candidate.scores?.opportunity)],
            ] as const;

            return (
              <li className="candidateCard" key={`${candidate.symbol}-${index}`}>
                <div className="candidateHeading">
                  <span className="rank">#{index + 1}</span>
                  <div>
                    <h2>
                      {finvizUrl ? (
                        <a
                          className="tickerLink"
                          href={finvizUrl}
                          rel="noreferrer"
                          target="_blank"
                          title={`在 Finviz 查看 ${symbol} 图表`}
                        >
                          {symbol}
                        </a>
                      ) : (
                        "—"
                      )}
                    </h2>
                    <p>{candidate.company ?? "公司名称待确认"}</p>
                  </div>
                  <strong className="totalScore">
                    {number(candidate.total_score, 1)}
                    <small>综合分</small>
                  </strong>
                </div>

                <div className="candidateMeta">
                  <span>
                    {strategyLabels[candidate.strategy ?? ""] ??
                      "策略候选"}
                  </span>
                  <span>
                    参考价 ${number(candidate.market_price, 2)}
                  </span>
                </div>

                <dl className="scoreGrid">
                  {candidateScores.map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value ?? "—"}</dd>
                    </div>
                  ))}
                </dl>

                <div className="candidateReason">
                  <h3>入选原因</h3>
                  <p>{candidate.catalyst ?? "等待补充研究证据。"}</p>
                </div>

                {candidate.pattern ? (
                  <div className="patternPanel">
                    <div className="patternHeading">
                      <div>
                        <span>图形识别</span>
                        <strong>
                          {candidate.pattern.name_zh ?? "待识别"}
                          {candidate.pattern.name_en
                            ? ` · ${candidate.pattern.name_en}`
                            : ""}
                        </strong>
                      </div>
                      <span className="patternStage">
                        {patternStageLabels[candidate.pattern.stage ?? ""] ??
                          "等待确认"}
                      </span>
                    </div>
                    <dl className="patternFacts">
                      <div>
                        <dt>关键价位</dt>
                        <dd>{candidate.pattern.key_level ?? "等待历史价格数据"}</dd>
                      </div>
                      <div>
                        <dt>成交量</dt>
                        <dd>
                          {candidate.pattern.volume_confirmation ??
                            "等待成交量确认"}
                        </dd>
                      </div>
                      <div>
                        <dt>确认条件</dt>
                        <dd>{candidate.pattern.confirmation ?? "等待确认"}</dd>
                      </div>
                      <div>
                        <dt>失效条件</dt>
                        <dd>{candidate.pattern.invalidation ?? "等待确认"}</dd>
                      </div>
                    </dl>
                  </div>
                ) : null}

                <div className="nextCheck">
                  <strong>下一步核查</strong>
                  <span>
                    {candidate.next_confirmation ??
                      "核对官方披露、估值与价格确认。"}
                  </span>
                </div>
                {finvizUrl ? (
                  <a
                    className="chartLink"
                    href={finvizUrl}
                    rel="noreferrer"
                    target="_blank"
                  >
                    查看 Finviz 图表 <span aria-hidden="true">↗</span>
                  </a>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="panel">
          <h2>今天没有合格观察候选</h2>
          <p className="message">系统不会为了填满榜单而降低标准。</p>
        </div>
      )}

      <div className="researchFooter">
        <p>
          数据时间：
          {report.generated_at
            ? new Date(report.generated_at).toLocaleString("zh-CN", {
                timeZone: "Australia/Melbourne",
              })
            : "待确认"}
        </p>
        <p>原始运行证据保留在后台，不在日常界面展示。</p>
      </div>
    </section>
  );
}
