"""Human-readable, evidence-bound research views for official news events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class NewsResearchCategory:
    code: str
    label: str
    source: str
    description: str
    matches: Callable[[str], bool]


NEWS_RESEARCH_CATEGORIES = (
    NewsResearchCategory(
        "fed_policy",
        "美联储政策",
        "Federal Reserve",
        "利率决定、政策声明与货币政策新闻。",
        lambda value: value == "macro_monetary_policy",
    ),
    NewsResearchCategory(
        "cpi",
        "CPI 消费者通胀",
        "U.S. Bureau of Labor Statistics",
        "消费者价格变化及其对利率预期的影响。",
        lambda value: value == "macro_inflation_cpi",
    ),
    NewsResearchCategory(
        "ppi",
        "PPI 生产端通胀",
        "U.S. Bureau of Labor Statistics",
        "生产者价格变化与企业成本压力。",
        lambda value: value == "macro_inflation_ppi",
    ),
    NewsResearchCategory(
        "employment",
        "就业报告",
        "U.S. Bureau of Labor Statistics",
        "非农就业、失业率及工资压力。",
        lambda value: value == "macro_employment",
    ),
    NewsResearchCategory(
        "job_openings",
        "职位空缺",
        "U.S. Bureau of Labor Statistics",
        "JOLTS 职位空缺、招聘与离职趋势。",
        lambda value: value == "macro_job_openings",
    ),
    NewsResearchCategory(
        "sec_material",
        "SEC 重大申报",
        "SEC EDGAR",
        "观察名单公司的 8-K 重大事项。",
        lambda value: value.startswith("sec_8-k"),
    ),
    NewsResearchCategory(
        "sec_earnings",
        "业绩与定期申报",
        "SEC EDGAR",
        "观察名单公司的 10-Q 与 10-K。",
        lambda value: value.startswith(("sec_10-q", "sec_10-k")),
    ),
    NewsResearchCategory(
        "institutional",
        "机构与大股东持仓",
        "SEC EDGAR",
        "13F、13D 与 13G 持仓披露。",
        lambda value: value.startswith(("sec_13", "institutional_", "beneficial_")),
    ),
    NewsResearchCategory(
        "insider",
        "内部人士交易",
        "SEC EDGAR",
        "Form 4 内部人士买卖披露。",
        lambda value: value.startswith(("sec_4", "insider_")),
    ),
)


def _category_for(event_type: str) -> NewsResearchCategory | None:
    return next(
        (category for category in NEWS_RESEARCH_CATEGORIES if category.matches(event_type)),
        None,
    )


def _research_lens(event_type: str) -> dict[str, str]:
    if event_type == "macro_monetary_policy":
        return {
            "summary": "这是美联储官方货币政策更新，重点是政策利率、声明措辞和未来路径是否改变。",
            "trading_focus": "观察美债收益率、美元、主要指数与利率敏感板块是否出现同方向确认。",
            "investing_focus": "判断资本成本和估值折现率是否发生持续变化，而不是只看发布当日波动。",
        }
    if event_type == "macro_inflation_cpi":
        return {
            "summary": "这是官方消费者通胀更新，需区分总体、核心及月度趋势。",
            "trading_focus": "比较数据与市场预期，并观察收益率、成长股及防御板块的反应。",
            "investing_focus": "评估通胀趋势是否会改变利率路径、消费能力和企业定价权。",
        }
    if event_type == "macro_inflation_ppi":
        return {
            "summary": "这是官方生产端通胀更新，用于观察企业投入成本压力。",
            "trading_focus": "关注成本敏感行业、收益率和通胀预期是否同步变化。",
            "investing_focus": "检查观察名单公司的毛利率能否承受成本变化，及其是否具备转嫁能力。",
        }
    if event_type == "macro_employment":
        return {
            "summary": "这是官方就业更新，核心是就业增长、失业率和工资增速之间的组合。",
            "trading_focus": "观察数据相对预期的偏差，以及指数、收益率和周期板块的确认。",
            "investing_focus": "判断劳动力市场对消费需求、工资成本及经济周期的中期影响。",
        }
    if event_type == "macro_job_openings":
        return {
            "summary": "这是 JOLTS 劳动力需求更新，需结合招聘、离职和职位空缺趋势判断。",
            "trading_focus": "观察利率预期是否变化，避免只凭单一职位空缺数字交易。",
            "investing_focus": "评估劳动力需求是否持续降温，以及对工资和企业利润率的影响。",
        }
    if event_type.startswith("sec_8-k"):
        return {
            "summary": "这是观察名单公司的 8-K 重大事项申报；具体影响取决于披露项目。",
            "trading_focus": "核对申报事项、发布时间、价格缺口、成交量与后续管理层说明。",
            "investing_focus": "判断事项是否改变盈利能力、资本结构、管理层、并购或长期风险。",
        }
    if event_type.startswith(("sec_10-q", "sec_10-k")):
        return {
            "summary": "这是定期业绩申报；标题本身不能证明业绩改善或恶化。",
            "trading_focus": "对比收入、利润、指引与市场预期，并观察业绩后的价格和成交量确认。",
            "investing_focus": "重点检查现金流、利润率、资产负债表、风险披露和管理层展望的变化。",
        }
    if event_type.startswith(("sec_13", "institutional_", "beneficial_")):
        return {
            "summary": "这是机构或大股东持仓披露；申报存在时间滞后，不能视为即时买卖信号。",
            "trading_focus": "比较前后持仓变化、集中度及价格反应，不追随单一机构动作。",
            "investing_focus": "判断持仓变化是否支持长期论点，并核对申报期与当前基本面差异。",
        }
    if event_type.startswith(("sec_4", "insider_")):
        return {
            "summary": "这是内部人士交易披露，需区分主动公开市场交易、期权行权和预设计划。",
            "trading_focus": "重点关注多名内部人集中主动买入及随后成交量确认。",
            "investing_focus": "结合内部人角色、交易金额、既有持仓和公司估值判断信号质量。",
        }
    return {
        "summary": "这是已核验的官方事件；现有证据不足以得出方向性结论。",
        "trading_focus": "等待价格、成交量和相关市场的确认。",
        "investing_focus": "核对事件是否改变公司的长期现金流、风险或估值。",
    }


def build_news_research_board(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return complete coverage and concise research lenses without source-link handoffs."""

    categorised: dict[str, list[dict[str, Any]]] = {
        category.code: [] for category in NEWS_RESEARCH_CATEGORIES
    }
    items: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type", ""))
        category = _category_for(event_type)
        if category is None:
            continue
        lens = _research_lens(event_type)
        ai_summary = event.get("ai_summary")
        if isinstance(ai_summary, dict):
            lens = {
                "summary": str(ai_summary.get("summary") or lens["summary"]),
                "trading_focus": str(
                    ai_summary.get("trading_focus") or lens["trading_focus"]
                ),
                "investing_focus": str(
                    ai_summary.get("investing_focus") or lens["investing_focus"]
                ),
            }
        item = {
            "headline": event.get("headline"),
            "symbols": event.get("symbols") or [],
            "event_type": event_type,
            "category": category.code,
            "category_label": category.label,
            "source": event.get("source"),
            "source_tier": event.get("source_tier"),
            "published_at": event.get("published_at"),
            "significance": event.get("significance"),
            "confidence": event.get("confidence"),
            **lens,
            "missing_information": (
                str(ai_summary.get("missing_information"))
                if isinstance(ai_summary, dict) and ai_summary.get("missing_information")
                else "LMIO 只保存了官方标题与申报元数据；方向、数字和市场影响必须继续核实。"
            ),
            "system_action": "进入研究流程；不创建或执行订单。",
            "analysis_method": (
                "openai_responses_v1"
                if isinstance(ai_summary, dict)
                else "evidence_bound_research_v1"
            ),
        }
        categorised[category.code].append(item)
        items.append(item)

    coverage = []
    for category in NEWS_RESEARCH_CATEGORIES:
        matches = categorised[category.code]
        coverage.append(
            {
                "code": category.code,
                "label": category.label,
                "source": category.source,
                "description": category.description,
                "status": "available" if matches else "waiting_for_verified_release",
                "event_count": len(matches),
                "latest_published_at": matches[0].get("published_at") if matches else None,
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "coverage": coverage,
        "events": items,
        "source_policy": "Free official sources: Federal Reserve, BLS and SEC EDGAR.",
        "analysis_boundary": (
            "Summaries are evidence-bound research aids. They do not predict direction, "
            "approve an investment or trigger a trade."
        ),
    }
