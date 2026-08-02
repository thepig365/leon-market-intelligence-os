"""Deterministic, evidence-aware Top 10 ranking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from pydantic import BaseModel, Field

from lmio.domain import ScreenCandidate


class RankedCandidate(BaseModel):
    candidate_id: str
    candidate: ScreenCandidate
    rank: int = Field(ge=1)
    adjusted_score: float = Field(ge=0, le=100)
    ranking_reasons: list[str]
    alternative_strategies: list[str] = Field(default_factory=list)


def candidate_identifier(run_id: str, candidate: ScreenCandidate) -> str:
    raw = f"{run_id}:{candidate.symbol.upper()}:{candidate.strategy.value}"
    return f"candidate-{sha256(raw.encode()).hexdigest()[:20]}"


def rank_top10(
    candidates: list[ScreenCandidate],
    *,
    run_id: str,
    now: datetime | None = None,
    require_operational: bool = True,
) -> list[RankedCandidate]:
    """Rank once per symbol independent of screen execution order.

    Confidence, completeness, missing evidence and stale observations affect the
    score explicitly. Non-operational provenance never enters an operational
    ranking. When several strategies match one symbol, the strongest adjusted
    candidate is retained and the remaining strategies remain visible.
    """

    current = now or datetime.now(UTC)
    grouped: dict[str, list[tuple[ScreenCandidate, float, list[str]]]] = {}
    for candidate in candidates:
        if require_operational and not candidate.provenance.operational:
            continue
        observed = max((item.observed_at for item in candidate.evidence), default=current)
        stale = current - observed > timedelta(hours=24)
        confidence_penalty = (1 - candidate.scores.confidence) * 20
        completeness_penalty = (1 - candidate.source_completeness) * 20
        missing_penalty = min(25, len(candidate.missing_fields) * 5)
        stale_penalty = 15 if stale else 0
        adjusted = max(
            0,
            min(
                100,
                candidate.total_score
                - confidence_penalty
                - completeness_penalty
                - missing_penalty
                - stale_penalty,
            ),
        )
        reasons = [
            f"raw_score={candidate.total_score:.4f}",
            f"confidence_penalty={confidence_penalty:.4f}",
            f"completeness_penalty={completeness_penalty:.4f}",
            f"missing_evidence_penalty={missing_penalty:.4f}",
            f"stale_penalty={stale_penalty:.4f}",
            f"provenance={candidate.provenance.value}",
        ]
        grouped.setdefault(candidate.symbol.upper(), []).append((candidate, adjusted, reasons))

    selected: list[tuple[ScreenCandidate, float, list[str], list[str]]] = []
    for symbol, options in grouped.items():
        ordered = sorted(
            options,
            key=lambda item: (
                -item[1],
                -item[0].total_score,
                item[0].strategy.value,
                symbol,
            ),
        )
        winner, adjusted, reasons = ordered[0]
        alternatives = sorted(item[0].strategy.value for item in ordered[1:])
        if alternatives:
            reasons.append("duplicate_symbol_strategies_deduplicated")
        selected.append((winner, adjusted, reasons, alternatives))

    ordered_selected = sorted(
        selected,
        key=lambda item: (
            -item[1],
            -item[0].total_score,
            item[0].symbol.upper(),
            item[0].strategy.value,
        ),
    )[:10]
    return [
        RankedCandidate(
            candidate_id=candidate_identifier(run_id, candidate),
            candidate=candidate,
            rank=index,
            adjusted_score=round(adjusted, 4),
            ranking_reasons=reasons,
            alternative_strategies=alternatives,
        )
        for index, (candidate, adjusted, reasons, alternatives) in enumerate(
            ordered_selected, start=1
        )
    ]
