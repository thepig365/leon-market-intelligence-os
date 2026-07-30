"""Deterministic four-dimension scoring with explicit missing-data penalties."""

from statistics import fmean

from lmio.domain import DimensionScores, SecuritySnapshot, Strategy

CALCULATION_VERSION = "scores-v1"


def _linear(value: float | None, low: float, high: float, *, inverse: bool = False) -> float:
    if value is None:
        return 50
    bounded = max(0.0, min(1.0, (value - low) / (high - low)))
    return round((1 - bounded if inverse else bounded) * 100, 2)


def score_snapshot(item: SecuritySnapshot) -> DimensionScores:
    quality_values = [
        _linear(item.revenue_growth_pct, 0, 30),
        _linear(item.eps_growth_pct, 0, 30),
        _linear(item.gross_margin_pct, 20, 80),
        _linear(item.operating_margin_pct, 0, 35),
        _linear(item.roic_pct, 0, 30),
        _linear(item.debt_to_equity, 0, 2, inverse=True),
        _linear(item.fcf_margin_pct, 0, 30),
    ]
    valuation_values = [
        _linear(item.fcf_margin_pct, 0, 30),
        _linear(item.debt_to_equity, 0, 2, inverse=True),
    ]
    opportunity_values = [
        _linear(item.earnings_revision_30d_pct, -10, 15),
        _linear(item.earnings_surprise_pct, -10, 20),
        _linear(item.sector_strength, 0, 100),
    ]
    timing_values = [
        _linear(item.relative_strength_6m, -30, 50),
        _linear(item.price_above_200d_pct, -30, 30),
        _linear(item.relative_volume, 0.5, 3),
    ]
    available = sum(
        value is not None
        for value in (
            item.revenue_growth_pct,
            item.eps_growth_pct,
            item.gross_margin_pct,
            item.operating_margin_pct,
            item.roic_pct,
            item.debt_to_equity,
            item.fcf_margin_pct,
            item.relative_strength_6m,
            item.price_above_200d_pct,
            item.earnings_revision_30d_pct,
            item.earnings_surprise_pct,
            item.relative_volume,
            item.sector_strength,
        )
    )
    completeness = available / 13
    confidence = round(min(item.data_completeness, completeness), 3)
    penalty = 0.7 + (0.3 * confidence)

    return DimensionScores(
        quality=round(fmean(quality_values) * penalty, 2),
        valuation=round(fmean(valuation_values) * penalty, 2),
        opportunity=round(fmean(opportunity_values) * penalty, 2),
        timing=round(fmean(timing_values) * penalty, 2),
        confidence=confidence,
        calculation_version=CALCULATION_VERSION,
    )


def weighted_total(scores: DimensionScores, strategy: Strategy) -> float:
    if strategy in {
        Strategy.EARNINGS_REVISION_MOMENTUM,
        Strategy.PEAD,
        Strategy.NEWS_DRIVEN,
    }:
        weights = (0.2, 0.1, 0.4, 0.3)
    elif strategy in {
        Strategy.INSTITUTIONAL_ACCUMULATION,
        Strategy.ACTIVIST_CATALYST,
        Strategy.INSIDER_VALUE,
    }:
        weights = (0.25, 0.25, 0.35, 0.15)
    elif strategy in {Strategy.OVERSOLD_REVERSAL, Strategy.SHORT_SQUEEZE}:
        weights = (0.15, 0.15, 0.25, 0.45)
    else:
        weights = (0.3, 0.3, 0.2, 0.2)
    values = (scores.quality, scores.valuation, scores.opportunity, scores.timing)
    return round(sum(value * weight for value, weight in zip(values, weights, strict=True)), 2)
