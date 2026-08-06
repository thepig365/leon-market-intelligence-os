"""Deterministic provider-batch quality checks used before core calculations."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, Field

from lmio.domain import SecuritySnapshot


class BatchState(StrEnum):
    VALID = "valid"
    EMPTY = "empty"
    STALE = "stale"
    DUPLICATE = "duplicate"
    OUT_OF_ORDER = "out_of_order"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"


class BatchAssessment(BaseModel):
    state: BatchState
    accepted: bool
    item_count: int = Field(ge=0)
    issues: list[str]


def assess_snapshot_batch(
    items: list[SecuritySnapshot],
    *,
    now: datetime | None = None,
    max_age: timedelta = timedelta(hours=24),
) -> BatchAssessment:
    if not items:
        return BatchAssessment(
            state=BatchState.EMPTY,
            accepted=False,
            item_count=0,
            issues=["provider returned no snapshots"],
        )
    observed_now = now or datetime.now(UTC)
    symbols = [item.symbol.upper() for item in items]
    if len(symbols) != len(set(symbols)):
        return BatchAssessment(
            state=BatchState.DUPLICATE,
            accepted=False,
            item_count=len(items),
            issues=["duplicate symbols in provider batch"],
        )
    timestamps = [item.observed_at for item in items]
    if timestamps != sorted(timestamps):
        return BatchAssessment(
            state=BatchState.OUT_OF_ORDER,
            accepted=False,
            item_count=len(items),
            issues=["provider observations are not time ordered"],
        )
    if any(observed_now - item.observed_at > max_age for item in items):
        return BatchAssessment(
            state=BatchState.STALE,
            accepted=False,
            item_count=len(items),
            issues=["one or more provider observations are stale"],
        )
    issues = [
        f"{item.symbol}: low data completeness" for item in items if item.data_completeness < 0.7
    ]
    return BatchAssessment(
        state=BatchState.DEGRADED if issues else BatchState.VALID,
        accepted=True,
        item_count=len(items),
        issues=issues,
    )


def classify_provider_failure(error: Exception) -> BatchState:
    name = type(error).__name__.lower()
    message = str(error).lower()
    if "rate" in name or "429" in message or "rate limit" in message:
        return BatchState.RATE_LIMITED
    return BatchState.UNAVAILABLE
