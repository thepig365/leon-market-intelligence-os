from datetime import UTC, datetime

from lmio.domain import NewsEvent
from lmio.news import deduplicate_events, news_impact_score


def event(source: str, tier: int, confidence: float) -> NewsEvent:
    return NewsEvent(
        headline="Company files Form 8-K",
        source=source,
        source_url=f"https://example.test/{source}",
        source_tier=tier,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        symbols=["TEST"],
        event_type="sec_filing",
        significance=80,
        surprise=20,
        confidence=confidence,
    )


def test_duplicate_prefers_official_source() -> None:
    events = deduplicate_events([event("secondary", 2, 0.9), event("SEC", 1, 0.8)])

    assert len(events) == 1
    assert events[0].source == "SEC"


def test_impact_is_bounded() -> None:
    assert 0 <= news_impact_score(event("SEC", 1, 0.8)) <= 100
