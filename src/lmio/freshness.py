"""Data-type-specific freshness contracts for API, dashboard and alerts."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FreshnessState(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class DataType(StrEnum):
    MARKET_SNAPSHOT = "market_snapshot"
    PRICE_CONFIRMATION = "price_confirmation"
    MACRO_RELEASE = "macro_release"
    SEC_FILING = "sec_filing"
    INSTITUTIONAL_OWNERSHIP = "institutional_ownership"
    VALUATION = "valuation"
    RESEARCH_PACKAGE = "research_package"
    TOP_10 = "top_10"
    TOP_3 = "top_3"
    CONDITIONAL_PLAN = "conditional_plan"


# Deliberately separate thresholds: ownership changes quarterly while market
# and price confirmation data become misleading within a session.
THRESHOLDS_SECONDS: dict[DataType, tuple[int, int]] = {
    DataType.MARKET_SNAPSHOT: (15 * 60, 60 * 60),
    DataType.PRICE_CONFIRMATION: (5 * 60, 20 * 60),
    DataType.MACRO_RELEASE: (6 * 60 * 60, 24 * 60 * 60),
    DataType.SEC_FILING: (12 * 60 * 60, 48 * 60 * 60),
    DataType.INSTITUTIONAL_OWNERSHIP: (45 * 24 * 60 * 60, 100 * 24 * 60 * 60),
    DataType.VALUATION: (24 * 60 * 60, 7 * 24 * 60 * 60),
    DataType.RESEARCH_PACKAGE: (8 * 60 * 60, 24 * 60 * 60),
    DataType.TOP_10: (60 * 60, 8 * 60 * 60),
    DataType.TOP_3: (60 * 60, 8 * 60 * 60),
    DataType.CONDITIONAL_PLAN: (24 * 60 * 60, 5 * 24 * 60 * 60),
}


class Freshness(BaseModel):
    as_of: datetime | None
    retrieved_at: datetime
    age_seconds: int | None = Field(default=None, ge=0)
    freshness_state: FreshnessState
    source: str
    snapshot_id: str


def evaluate_freshness(
    data_type: DataType,
    *,
    as_of: datetime | None,
    retrieved_at: datetime,
    source: str,
    snapshot_id: str,
    now: datetime | None = None,
) -> Freshness:
    current = now or datetime.now(UTC)
    if as_of is None:
        return Freshness(
            as_of=None,
            retrieved_at=retrieved_at,
            freshness_state=FreshnessState.UNKNOWN,
            source=source,
            snapshot_id=snapshot_id,
        )
    age = max(0, int((current - as_of).total_seconds()))
    fresh_limit, stale_limit = THRESHOLDS_SECONDS[data_type]
    if age <= fresh_limit:
        state = FreshnessState.FRESH
    elif age <= stale_limit:
        state = FreshnessState.AGING
    else:
        state = FreshnessState.STALE
    return Freshness(
        as_of=as_of,
        retrieved_at=retrieved_at,
        age_seconds=age,
        freshness_state=state,
        source=source,
        snapshot_id=snapshot_id,
    )


def blocks_new_recommendation(data_type: DataType, freshness: Freshness) -> bool:
    critical = {DataType.MARKET_SNAPSHOT, DataType.PRICE_CONFIRMATION}
    return data_type in critical and freshness.freshness_state in {
        FreshnessState.STALE,
        FreshnessState.UNKNOWN,
    }
