from datetime import UTC, datetime, timedelta

from lmio.domain import NewsEvent
from lmio.news_price import ConfirmationState, PriceWindow, assess_news_price


def event() -> NewsEvent:
    return NewsEvent(
        headline="Issuer reports verified quarterly results",
        source="Issuer IR",
        source_url="https://example.test/release",
        source_tier=1,
        published_at=datetime(2026, 8, 2, 12, tzinfo=UTC),
        symbols=["TEST"],
        event_type="earnings",
        significance=80,
        surprise=10,
        confidence=0.9,
    )


def test_news_alone_remains_pending_without_price_verification() -> None:
    result = assess_news_price(
        event(),
        ingestion_time=datetime(2026, 8, 2, 12, 1, tzinfo=UTC),
        pre_event=None,
        post_event=[],
    )
    assert result.confirmation_state is ConfirmationState.PENDING
    assert "pre_event_price" in result.missing_evidence
    assert "parsed_event_specific_explanation" in result.missing_evidence


def test_verified_event_and_price_windows_can_confirm_market_acceptance() -> None:
    pre = PriceWindow(
        observed_at=datetime(2026, 8, 2, 11, 59, tzinfo=UTC),
        price=100,
        benchmark_price=500,
    )
    post = PriceWindow(
        observed_at=pre.observed_at + timedelta(minutes=30),
        price=106,
        benchmark_price=505,
        relative_volume=1.5,
        vwap=103,
        opening_range_high=104,
        opening_range_low=99,
    )
    result = assess_news_price(
        event(),
        ingestion_time=datetime(2026, 8, 2, 12, 1, tzinfo=UTC),
        pre_event=pre,
        post_event=[post],
        explanation="Revenue and guidance exceeded the filed prior-period comparison.",
        transmission_mechanism="Higher guidance changes forward earnings expectations.",
    )
    assert result.confirmation_state is ConfirmationState.CONFIRMED
    assert result.abnormal_return_vs_benchmark == 0.05
    assert result.vwap_position == "above"
    assert result.opening_range_behaviour == "breakout_above"
