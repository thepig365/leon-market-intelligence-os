from datetime import UTC, datetime

from lmio.domain import NewsEvent
from lmio.news_plan import propose_news_plan


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
