"""Translate important verified news into conditional research plans."""

from lmio.domain import NewsEvent
from lmio.news import news_impact_score
from lmio.plans import ConditionalPlan


def propose_news_plan(
    event: NewsEvent,
    *,
    price_confirmation: bool,
    evidence_urls: list[str],
) -> ConditionalPlan | None:
    """Return a research plan only when official evidence and price confirmation exist."""

    if event.source_tier > 2 or news_impact_score(event) < 55 or not price_confirmation:
        return None
    if not event.symbols:
        return None
    return ConditionalPlan(
        symbol=event.symbols[0],
        thesis=f"{event.event_type}: {event.headline}",
        confirmation_condition="Price, volume and reaction-window evidence remain confirmed.",
        invalidation_condition="Official evidence reverses or the reaction fails its reference.",
        entry_zone="Derived only after deterministic market-data confirmation.",
        stop_reference="Event reaction support; calculation required.",
        target_reference="Next material resistance; calculation required.",
        risk_reward=2,
        evidence_urls=sorted(set([event.source_url, *evidence_urls])),
    )
