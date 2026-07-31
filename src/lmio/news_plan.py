"""Translate important verified news into conditional research plans."""

from typing import Literal

from pydantic import BaseModel, Field

from lmio.domain import NewsEvent
from lmio.news import news_impact_score
from lmio.plans import ConditionalPlan


class ReactionEvidence(BaseModel):
    window_minutes: int = Field(ge=1, le=1440)
    stock_return_pct: float
    benchmark_return_pct: float
    relative_volume: float = Field(ge=0)
    direction: Literal["bullish", "bearish"] = "bullish"
    vwap_confirmed: bool = False
    opening_range_confirmed: bool = False
    gap_retention_pct: float | None = Field(default=None, ge=0, le=100)

    @property
    def abnormal_return_pct(self) -> float:
        return round(self.stock_return_pct - self.benchmark_return_pct, 2)

    @property
    def direction_confirmed(self) -> bool:
        if self.direction == "bullish":
            return self.abnormal_return_pct >= 1
        return self.abnormal_return_pct <= -1

    @property
    def structure_confirmed(self) -> bool:
        gap_confirmed = self.gap_retention_pct is None or self.gap_retention_pct >= 50
        return (
            self.window_minutes >= 30
            and self.vwap_confirmed
            and self.opening_range_confirmed
            and gap_confirmed
        )

    @property
    def confirmed(self) -> bool:
        return self.direction_confirmed and self.relative_volume >= 1.2 and self.structure_confirmed


def propose_news_plan(
    event: NewsEvent,
    *,
    price_confirmation: bool,
    evidence_urls: list[str],
    reaction: ReactionEvidence | None = None,
) -> ConditionalPlan | None:
    """Return a research plan only when official evidence and price confirmation exist."""

    reaction_confirmed = reaction.confirmed if reaction is not None else price_confirmation
    if event.source_tier > 2 or news_impact_score(event) < 70 or not reaction_confirmed:
        return None
    if not event.symbols:
        return None
    return ConditionalPlan(
        symbol=event.symbols[0],
        thesis=(
            f"{reaction.direction if reaction is not None else 'conditional'} "
            f"{event.event_type}: {event.headline}"
        ),
        confirmation_condition=(
            "Price, relative volume, VWAP, opening range and reaction-window evidence "
            "remain confirmed"
            + (
                f" ({reaction.window_minutes}m abnormal return "
                f"{reaction.abnormal_return_pct:+.2f}%)."
                if reaction is not None
                else "."
            )
        ),
        invalidation_condition="Official evidence reverses or the reaction fails its reference.",
        entry_zone="Derived only after deterministic market-data confirmation.",
        stop_reference="Event reaction support; calculation required.",
        target_reference="Next material resistance; calculation required.",
        risk_reward=2,
        evidence_urls=sorted(set([event.source_url, *evidence_urls])),
    )
