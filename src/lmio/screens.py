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


def run_core_screens(items: list[SecuritySnapshot]) -> list[ScreenCandidate]:
    candidates: list[ScreenCandidate] = []
    for item in items:
        strategies: list[Strategy] = []
        if quality_growth_passes(item):
            strategies.append(Strategy.QUALITY_GROWTH_MOMENTUM)
        if earnings_revision_passes(item):
            strategies.append(Strategy.EARNINGS_REVISION_MOMENTUM)
        for strategy in strategies:
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
            catalyst = (
                "盈利预期上修且价格保持相对强势"
                if strategy is Strategy.EARNINGS_REVISION_MOMENTUM
                else "质量、增长与动量条件同时满足"
            )
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
                    catalyst=catalyst,
                    next_confirmation="核对最新官方披露、估值与价格确认",
                    invalidation="关键数据失效、指引转弱或价格结构破坏",
                    horizon="中期" if strategy is Strategy.QUALITY_GROWTH_MOMENTUM else "短至中期",
                    evidence=evidence,
                    missing_fields=missing_fields(item),
                )
            )
    return sorted(candidates, key=lambda candidate: (-candidate.total_score, candidate.symbol))
