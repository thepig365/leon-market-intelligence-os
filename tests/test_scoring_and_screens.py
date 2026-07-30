from lmio.demo import demo_universe
from lmio.domain import Strategy
from lmio.scoring import score_snapshot, weighted_total
from lmio.screens import run_core_screens
from lmio.universe import build_investable_universe


def test_missing_data_reduces_confidence_and_scores() -> None:
    complete = demo_universe()[0]
    incomplete = complete.model_copy(
        update={
            "revenue_growth_pct": None,
            "eps_growth_pct": None,
            "roic_pct": None,
            "earnings_revision_30d_pct": None,
        }
    )

    complete_scores = score_snapshot(complete)
    incomplete_scores = score_snapshot(incomplete)

    assert incomplete_scores.confidence < complete_scores.confidence
    assert incomplete_scores.quality < complete_scores.quality


def test_strategy_weights_are_not_identical() -> None:
    scores = score_snapshot(demo_universe()[0])

    assert weighted_total(scores, Strategy.QUALITY_GROWTH_MOMENTUM) != weighted_total(
        scores, Strategy.EARNINGS_REVISION_MOMENTUM
    )


def test_core_screens_preserve_strategy_and_evidence() -> None:
    candidates = run_core_screens(build_investable_universe(demo_universe()))

    assert candidates
    assert all(candidate.evidence for candidate in candidates)
    assert {candidate.strategy for candidate in candidates} >= {
        Strategy.QUALITY_GROWTH_MOMENTUM,
        Strategy.EARNINGS_REVISION_MOMENTUM,
    }
