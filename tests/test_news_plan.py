from datetime import UTC, datetime

from lmio.domain import NewsEvent
from lmio.news_plan import ReactionEvidence, propose_news_plan


def event(tier: int = 1, significance: float = 90) -> NewsEvent:
    return NewsEvent(
        headline="Official guidance changed materially",
        source="SEC EDGAR",
        source_url="https://www.sec.gov/example",
        source_tier=tier,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        symbols=["TEST"],
        event_type="guidance",
        significance=significance,
        surprise=30,
        confidence=1,
    )


def test_news_needs_price_confirmation() -> None:
    assert propose_news_plan(event(), price_confirmation=False, evidence_urls=[]) is None


def test_verified_news_creates_research_plan_not_order() -> None:
    plan = propose_news_plan(event(), price_confirmation=True, evidence_urls=[])

    assert plan is not None
    assert plan.symbol == "TEST"
    assert not hasattr(plan, "order")
    assert not hasattr(plan, "quantity")


def test_low_quality_source_is_rejected() -> None:
    assert propose_news_plan(event(tier=3), price_confirmation=True, evidence_urls=[]) is None


def test_reaction_window_requires_abnormal_return_and_volume() -> None:
    weak = ReactionEvidence(
        window_minutes=30,
        stock_return_pct=2,
        benchmark_return_pct=1.5,
        relative_volume=2,
        vwap_confirmed=True,
        opening_range_confirmed=True,
    )
    strong = weak.model_copy(update={"stock_return_pct": 3})

    assert (
        propose_news_plan(
            event(),
            price_confirmation=True,
            evidence_urls=[],
            reaction=weak,
        )
        is None
    )
    assert (
        propose_news_plan(
            event(),
            price_confirmation=False,
            evidence_urls=[],
            reaction=strong,
        )
        is not None
    )


def test_reaction_window_requires_vwap_opening_range_and_gap_retention() -> None:
    base = ReactionEvidence(
        window_minutes=30,
        stock_return_pct=3,
        benchmark_return_pct=1,
        relative_volume=2,
    )
    assert base.confirmed is False
    assert (
        base.model_copy(
            update={
                "vwap_confirmed": True,
                "opening_range_confirmed": True,
                "gap_retention_pct": 40,
            }
        ).confirmed
        is False
    )
    assert (
        base.model_copy(
            update={
                "vwap_confirmed": True,
                "opening_range_confirmed": True,
                "gap_retention_pct": 60,
            }
        ).confirmed
        is True
    )


def test_bearish_reaction_can_create_a_conditional_plan() -> None:
    reaction = ReactionEvidence(
        window_minutes=60,
        stock_return_pct=-4,
        benchmark_return_pct=-1,
        relative_volume=2,
        direction="bearish",
        vwap_confirmed=True,
        opening_range_confirmed=True,
        gap_retention_pct=80,
    )

    plan = propose_news_plan(
        event(),
        price_confirmation=False,
        evidence_urls=[],
        reaction=reaction,
    )

    assert plan is not None
    assert plan.thesis.startswith("bearish")
