"""Event-specific news/price confirmation; news alone never becomes a signal."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from lmio.domain import NewsEvent


class ConfirmationState(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


class PriceWindow(BaseModel):
    observed_at: datetime
    price: float = Field(gt=0)
    benchmark_price: float = Field(gt=0)
    relative_volume: float | None = Field(default=None, ge=0)
    vwap: float | None = Field(default=None, gt=0)
    opening_range_high: float | None = Field(default=None, gt=0)
    opening_range_low: float | None = Field(default=None, gt=0)


class NewsPriceConfirmation(BaseModel):
    original_source: str
    source_url: str
    publication_time: datetime
    ingestion_time: datetime
    event_type: str
    affected_symbols: list[str]
    significance: float
    source_quality: int
    event_specific_explanation: str
    expected_transmission_mechanism: str
    pre_event_price: float | None
    post_event_price_windows: list[PriceWindow]
    abnormal_return_vs_benchmark: float | None
    relative_volume: float | None
    vwap_position: str
    opening_range_behaviour: str
    gap_retention: str
    confirmation_state: ConfirmationState
    invalidation_state: str
    next_review_time: datetime | None
    missing_evidence: list[str] = Field(default_factory=list)


def assess_news_price(
    event: NewsEvent,
    *,
    ingestion_time: datetime,
    pre_event: PriceWindow | None,
    post_event: list[PriceWindow],
    explanation: str | None = None,
    transmission_mechanism: str | None = None,
    next_review_time: datetime | None = None,
) -> NewsPriceConfirmation:
    """Assess verified windows and fail closed when event content or prices are absent."""

    missing: list[str] = []
    if pre_event is None:
        missing.append("pre_event_price")
    if not post_event:
        missing.append("post_event_price_windows")
    if not explanation:
        missing.append("parsed_event_specific_explanation")
    if not transmission_mechanism:
        missing.append("expected_transmission_mechanism")
    abnormal: float | None = None
    relative_volume: float | None = None
    vwap_position = "unknown"
    opening_range = "unknown"
    gap_retention = "unknown"
    state = ConfirmationState.PENDING
    if pre_event is not None and post_event:
        latest = post_event[-1]
        stock_return = (latest.price - pre_event.price) / pre_event.price
        benchmark_return = (
            latest.benchmark_price - pre_event.benchmark_price
        ) / pre_event.benchmark_price
        abnormal = round(stock_return - benchmark_return, 6)
        relative_volume = latest.relative_volume
        if latest.vwap is not None:
            vwap_position = "above" if latest.price >= latest.vwap else "below"
        if latest.opening_range_high is not None and latest.price > latest.opening_range_high:
            opening_range = "breakout_above"
        elif latest.opening_range_low is not None and latest.price < latest.opening_range_low:
            opening_range = "breakdown_below"
        elif latest.opening_range_high is not None and latest.opening_range_low is not None:
            opening_range = "inside"
        gap = (latest.price - pre_event.price) / pre_event.price
        gap_retention = "positive" if gap > 0 else "negative_or_none"
        if not missing:
            volume_confirms = relative_volume is not None and relative_volume >= 1
            state = (
                ConfirmationState.CONFIRMED
                if abnormal > 0 and volume_confirms and vwap_position == "above"
                else ConfirmationState.REJECTED
            )
    return NewsPriceConfirmation(
        original_source=event.source,
        source_url=event.source_url,
        publication_time=event.published_at,
        ingestion_time=ingestion_time,
        event_type=event.event_type,
        affected_symbols=event.symbols,
        significance=event.significance,
        source_quality=event.source_tier,
        event_specific_explanation=(
            explanation or "Interpretation pending until filing or release content is parsed."
        ),
        expected_transmission_mechanism=(
            transmission_mechanism or "Pending verified event-specific interpretation."
        ),
        pre_event_price=pre_event.price if pre_event else None,
        post_event_price_windows=post_event,
        abnormal_return_vs_benchmark=abnormal,
        relative_volume=relative_volume,
        vwap_position=vwap_position,
        opening_range_behaviour=opening_range,
        gap_retention=gap_retention,
        confirmation_state=state,
        invalidation_state="not_evaluated" if missing else "active",
        next_review_time=next_review_time,
        missing_evidence=missing,
    )
