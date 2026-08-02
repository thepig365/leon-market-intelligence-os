"""Deterministic four-dimension scoring with explicit missing-data penalties."""

from statistics import fmean

from lmio.domain import DimensionScores, ScoreBreakdown, SecuritySnapshot, Strategy

CALCULATION_VERSION = "scores-v1"


def _linear(value: float | None, low: float, high: float, *, inverse: bool = False) -> float:
    if value is None:
        return 50
    bounded = max(0.0, min(1.0, (value - low) / (high - low)))
    return round((1 - bounded if inverse else bounded) * 100, 2)


def score_snapshot(item: SecuritySnapshot) -> DimensionScores:
    quality_inputs = {
        "revenue_growth_pct": item.revenue_growth_pct,
        "eps_growth_pct": item.eps_growth_pct,
        "gross_margin_pct": item.gross_margin_pct,
        "operating_margin_pct": item.operating_margin_pct,
        "roic_pct": item.roic_pct,
        "debt_to_equity": item.debt_to_equity,
        "fcf_margin_pct": item.fcf_margin_pct,
    }
    valuation_inputs = {
        "forward_pe": item.forward_pe,
        "fcf_margin_pct": item.fcf_margin_pct,
        "debt_to_equity": item.debt_to_equity,
    }
    opportunity_inputs = {
        "earnings_revision_30d_pct": item.earnings_revision_30d_pct,
        "earnings_surprise_pct": item.earnings_surprise_pct,
        "sector_strength": item.sector_strength,
    }
    timing_inputs = {
        "relative_strength_6m": item.relative_strength_6m,
        "price_above_200d_pct": item.price_above_200d_pct,
        "relative_volume": item.relative_volume,
    }
    quality_values = {
        "revenue_growth_pct": _linear(item.revenue_growth_pct, 0, 30),
        "eps_growth_pct": _linear(item.eps_growth_pct, 0, 30),
        "gross_margin_pct": _linear(item.gross_margin_pct, 20, 80),
        "operating_margin_pct": _linear(item.operating_margin_pct, 0, 35),
        "roic_pct": _linear(item.roic_pct, 0, 30),
        "debt_to_equity": _linear(item.debt_to_equity, 0, 2, inverse=True),
        "fcf_margin_pct": _linear(item.fcf_margin_pct, 0, 30),
    }
    valuation_values = {
        "forward_pe": _linear(item.forward_pe, 8, 45, inverse=True),
        "fcf_margin_pct": _linear(item.fcf_margin_pct, 0, 30),
        "debt_to_equity": _linear(item.debt_to_equity, 0, 2, inverse=True),
    }
    opportunity_values = {
        "earnings_revision_30d_pct": _linear(item.earnings_revision_30d_pct, -10, 15),
        "earnings_surprise_pct": _linear(item.earnings_surprise_pct, -10, 20),
        "sector_strength": _linear(item.sector_strength, 0, 100),
    }
    timing_values = {
        "relative_strength_6m": _linear(item.relative_strength_6m, -30, 50),
        "price_above_200d_pct": _linear(item.price_above_200d_pct, -30, 30),
        "relative_volume": _linear(item.relative_volume, 0.5, 3),
    }
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
            item.forward_pe,
        )
    )
    completeness = available / 14
    confidence = round(min(item.data_completeness, completeness), 3)
    penalty = 0.7 + (0.3 * confidence)

    evidence = [item.source_url] if item.source_url else [f"provider:{item.source}"]
    calculated_at = item.observed_at

    def breakdown(
        inputs: dict[str, float | None], values: dict[str, float], final_score: float
    ) -> ScoreBreakdown:
        weight = round(1 / len(inputs), 6)
        missing = [name for name, value in inputs.items() if value is None]
        return ScoreBreakdown(
            component_names=list(inputs),
            component_inputs=inputs,
            component_weights={name: weight for name in inputs},
            missing_inputs=missing,
            penalties={"confidence_multiplier": round(penalty, 6)},
            final_score=final_score,
            score_version=CALCULATION_VERSION,
            evidence_references=evidence,
            calculated_at=calculated_at,
        )

    quality = round(fmean(quality_values.values()) * penalty, 2)
    valuation = round(fmean(valuation_values.values()) * penalty, 2)
    opportunity = round(fmean(opportunity_values.values()) * penalty, 2)
    timing = round(fmean(timing_values.values()) * penalty, 2)
    return DimensionScores(
        quality=quality,
        valuation=valuation,
        opportunity=opportunity,
        timing=timing,
        confidence=confidence,
        calculation_version=CALCULATION_VERSION,
        breakdowns={
            "quality": breakdown(quality_inputs, quality_values, quality),
            "valuation": breakdown(valuation_inputs, valuation_values, valuation),
            "opportunity": breakdown(opportunity_inputs, opportunity_values, opportunity),
            "timing": breakdown(timing_inputs, timing_values, timing),
        },
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
    elif strategy in {
        Strategy.OVERSOLD_REVERSAL,
        Strategy.SHORT_SQUEEZE,
        Strategy.PATTERN_RECOGNITION,
    }:
        weights = (0.15, 0.15, 0.25, 0.45)
    else:
        weights = (0.3, 0.3, 0.2, 0.2)
    values = (scores.quality, scores.valuation, scores.opportunity, scores.timing)
    return round(sum(value * weight for value, weight in zip(values, weights, strict=True)), 2)
