"""Core V1 screen definitions and candidate evidence preservation."""

from lmio.domain import (
    CandidateState,
    EvidenceItem,
    ScreenCandidate,
    SecuritySnapshot,
    Strategy,
)
from lmio.scoring import score_snapshot, weighted_total

REQUIRED_FIELDS = (
    "revenue_growth_pct",
    "eps_growth_pct",
    "roic_pct",
    "debt_to_equity",
    "fcf_margin_pct",
    "relative_strength_6m",
    "earnings_revision_30d_pct",
)


def revision_breadth(upward: int, downward: int) -> float:
    """Return analyst revision breadth on a -100..100 scale."""
    if upward < 0 or downward < 0:
        raise ValueError("revision counts cannot be negative")
    total = upward + downward
    if total == 0:
        return 0
    return round((upward - downward) / total * 100, 2)


def eps_revision_pct(current: float, previous: float) -> float:
    if previous == 0:
        raise ValueError("previous EPS estimate cannot be zero")
    return round((current - previous) / abs(previous) * 100, 2)


def missing_fields(item: SecuritySnapshot) -> list[str]:
    return [field for field in REQUIRED_FIELDS if getattr(item, field) is None]


def quality_growth_passes(item: SecuritySnapshot) -> bool:
    return all(
        (
            (item.revenue_growth_pct or -100) >= 10,
            (item.eps_growth_pct or -100) >= 10,
            (item.roic_pct or -100) >= 10,
            (item.debt_to_equity if item.debt_to_equity is not None else 99) <= 1.5,
            (item.fcf_margin_pct or -100) >= 5,
            (item.relative_strength_6m or -100) >= 0,
        )
    )


def earnings_revision_passes(item: SecuritySnapshot) -> bool:
    return all(
        (
            (item.earnings_revision_30d_pct or -100) >= 2,
            (item.earnings_surprise_pct or -100) >= 0,
            (item.relative_strength_6m or -100) >= 0,
        )
    )


def _present(item: SecuritySnapshot, *fields: str) -> bool:
    return all(getattr(item, field) is not None for field in fields)


def strategies_for(item: SecuritySnapshot) -> list[Strategy]:
    strategies: list[Strategy] = []
    if quality_growth_passes(item):
        strategies.append(Strategy.QUALITY_GROWTH_MOMENTUM)
    if earnings_revision_passes(item):
        strategies.append(Strategy.EARNINGS_REVISION_MOMENTUM)
    if _present(item, "institutional_ownership_change_pct", "relative_volume") and (
        item.institutional_ownership_change_pct >= 2 and item.relative_volume >= 1
    ):
        strategies.append(Strategy.INSTITUTIONAL_ACCUMULATION)
    if item.activist_stake_pct is not None and item.activist_stake_pct >= 5:
        strategies.append(Strategy.ACTIVIST_CATALYST)
    if _present(item, "insider_net_buying_m", "forward_pe") and (
        item.insider_net_buying_m >= 0.25 and item.forward_pe <= 30
    ):
        strategies.append(Strategy.INSIDER_VALUE)
    if _present(item, "forward_pe", "eps_growth_pct", "roic_pct") and (
        0 < item.forward_pe <= 30 and item.eps_growth_pct >= 10 and item.roic_pct >= 10
    ):
        strategies.append(Strategy.QARP)
    if _present(
        item,
        "earnings_surprise_pct",
        "days_since_earnings",
        "post_earnings_return_pct",
    ) and (
        item.earnings_surprise_pct >= 5
        and 0 <= item.days_since_earnings <= 20
        and item.post_earnings_return_pct > 0
    ):
        strategies.append(Strategy.PEAD)
    if _present(item, "news_impact_score", "relative_volume") and (
        item.news_impact_score >= 70 and item.relative_volume >= 1.2
    ):
        strategies.append(Strategy.NEWS_DRIVEN)
    if _present(item, "rsi_14", "relative_volume", "earnings_revision_30d_pct") and (
        item.rsi_14 <= 30 and item.relative_volume >= 1.2 and item.earnings_revision_30d_pct >= 0
    ):
        strategies.append(Strategy.OVERSOLD_REVERSAL)
    if _present(
        item,
        "short_interest_float_pct",
        "days_to_cover",
        "relative_volume",
        "price_above_200d_pct",
    ) and (
        item.short_interest_float_pct >= 15
        and item.days_to_cover >= 3
        and item.relative_volume >= 1.5
        and item.price_above_200d_pct >= 0
    ):
        strategies.append(Strategy.SHORT_SQUEEZE)
    return strategies


CATALYSTS = {
    Strategy.QUALITY_GROWTH_MOMENTUM: "质量、增长与动量条件同时满足",
    Strategy.EARNINGS_REVISION_MOMENTUM: "盈利预期上修且价格保持相对强势",
    Strategy.INSTITUTIONAL_ACCUMULATION: "机构持仓增加并获得成交确认",
    Strategy.ACTIVIST_CATALYST: "已披露的积极股东持仓达到催化门槛",
    Strategy.INSIDER_VALUE: "内部人净买入与合理估值同时满足",
    Strategy.QARP: "盈利增长、资本回报与合理估值同时满足",
    Strategy.PEAD: "盈利超预期后价格延续确认",
    Strategy.NEWS_DRIVEN: "高影响新闻获得量价确认",
    Strategy.OVERSOLD_REVERSAL: "超卖、成交与基本面未恶化的组合确认",
    Strategy.SHORT_SQUEEZE: "高空头仓位、回补天数与量价突破组合确认",
}


def run_core_screens(items: list[SecuritySnapshot]) -> list[ScreenCandidate]:
    candidates: list[ScreenCandidate] = []
    for item in items:
        for strategy in strategies_for(item):
            scores = score_snapshot(item)
            total = weighted_total(scores, strategy)
            evidence = [
                EvidenceItem(
                    kind="normalised_snapshot",
                    summary=(
                        f"{item.symbol} passed {strategy.value}; "
                        f"calculation={scores.calculation_version}"
                    ),
                    source=item.source,
                    source_url=item.source_url,
                    observed_at=item.observed_at,
                    confidence=scores.confidence,
                )
            ]
            candidates.append(
                ScreenCandidate(
                    symbol=item.symbol,
                    company=item.company,
                    strategy=strategy,
                    state=(
                        CandidateState.RESEARCH_REQUIRED
                        if scores.confidence < 0.75
                        else CandidateState.SCREENED
                    ),
                    scores=scores,
                    total_score=total,
                    market_price=item.price,
                    catalyst=CATALYSTS[strategy],
                    next_confirmation="核对最新官方披露、估值与价格确认",
                    invalidation="关键数据失效、指引转弱或价格结构破坏",
                    horizon="中期" if strategy is Strategy.QUALITY_GROWTH_MOMENTUM else "短至中期",
                    evidence=evidence,
                    missing_fields=missing_fields(item),
                )
            )
    return sorted(candidates, key=lambda candidate: (-candidate.total_score, candidate.symbol))
