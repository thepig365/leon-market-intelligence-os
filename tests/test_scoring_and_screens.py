from lmio.demo import demo_universe
from lmio.domain import Strategy
from lmio.scoring import score_snapshot, weighted_total
from lmio.screens import eps_revision_pct, revision_breadth, run_core_screens, strategies_for
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


def test_revision_calculations_are_deterministic() -> None:
    assert revision_breadth(8, 2) == 60
    assert eps_revision_pct(1.2, 1) == 20


def test_combination_strategies_do_not_trigger_on_single_factor() -> None:
    item = demo_universe()[0].model_copy(
        update={
            "short_interest_float_pct": 25,
            "days_to_cover": None,
            "rsi_14": 25,
            "relative_volume": 0.8,
        }
    )

    strategies = strategies_for(item)

    assert Strategy.SHORT_SQUEEZE not in strategies
    assert Strategy.OVERSOLD_REVERSAL not in strategies


def test_all_active_v1_strategies_can_run_independently() -> None:
    item = demo_universe()[0].model_copy(
        update={
            "forward_pe": 20,
            "institutional_ownership_change_pct": 3,
            "activist_stake_pct": 6,
            "insider_net_buying_m": 1,
            "days_since_earnings": 5,
            "post_earnings_return_pct": 4,
            "rsi_14": 25,
            "short_interest_float_pct": 20,
            "days_to_cover": 5,
            "borrow_cost_pct": 8,
            "news_impact_score": 85,
            "relative_volume": 2,
        }
    )

    assert set(strategies_for(item)) == set(Strategy)
