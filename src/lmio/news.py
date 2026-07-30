"""Official-source news normalisation, deduplication and impact ranking."""

import hashlib
import re
from collections.abc import Iterable

from lmio.domain import NewsEvent

SPACE_PATTERN = re.compile(r"\s+")


def event_fingerprint(event: NewsEvent) -> str:
    normalised = SPACE_PATTERN.sub(" ", event.headline.strip().lower())
    symbol_key = ",".join(sorted(symbol.upper() for symbol in event.symbols))
    raw = f"{normalised}|{symbol_key}|{event.event_type}|{event.published_at.date()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def deduplicate_events(events: Iterable[NewsEvent]) -> list[NewsEvent]:
    """Prefer the strongest source tier then highest-confidence duplicate."""

    selected: dict[str, NewsEvent] = {}
    for event in events:
        key = event_fingerprint(event)
        existing = selected.get(key)
        if existing is None or (event.source_tier, -event.confidence) < (
            existing.source_tier,
            -existing.confidence,
        ):
            selected[key] = event
    return sorted(
        selected.values(),
        key=lambda event: (-event.significance, event.published_at, event.headline),
    )


def news_impact_score(event: NewsEvent) -> float:
    tier_weight = {1: 1.0, 2: 0.85, 3: 0.6}[event.source_tier]
    surprise_boost = min(abs(event.surprise), 100) * 0.25
    score = (event.significance * 0.75 + surprise_boost) * tier_weight * event.confidence
    return round(max(0, min(100, score)), 2)
