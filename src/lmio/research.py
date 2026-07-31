"""Structured evidence pack generation without unsupported AI invention."""

from pydantic import BaseModel, Field

from lmio.domain import NewsEvent, ScreenCandidate, ValuationResult
from lmio.news import news_impact_score


class ResearchPack(BaseModel):
    symbol: str
    company_profile: str
    what_changed: str
    why_now: str
    catalyst: str
    financial_quality: str
    earnings_revisions: str
    ownership_activity: str
    valuation_summary: str
    technical_context: str
    news_context: list[str]
    thesis: str
    supporting_evidence: list[str]
    contrary_evidence: list[str]
    risks: list[str]
    source_urls: list[str]
    missing_information: list[str]
    confidence: float = Field(ge=0, le=1)
    model_version: str = "deterministic-research-pack-v2"


def build_research_pack(
    candidate: ScreenCandidate,
    news: list[NewsEvent],
    valuation: ValuationResult | None,
) -> ResearchPack:
    related = [event for event in news if candidate.symbol in event.symbols]
    supporting = [item.summary for item in candidate.evidence if item.confidence >= 0.7]
    supporting.extend(
        f"{event.headline} (impact {news_impact_score(event):.1f})"
        for event in related
        if event.surprise >= 0
    )
    contrary = [
        event.headline for event in related if event.surprise < 0 or event.significance < 40
    ]
    risks = [candidate.invalidation]
    if valuation is None:
        risks.append("No reproducible valuation is attached.")
    elif valuation.safety_margin < 0:
        contrary.append(
            f"Multi-model value is below market price; safety margin {valuation.safety_margin:.1%}."
        )
    missing = list(candidate.missing_fields)
    confidence = candidate.scores.confidence
    if valuation is None:
        confidence *= 0.8
    if not related:
        confidence *= 0.9
    urls = {
        url
        for url in (
            [item.source_url for item in candidate.evidence]
            + [event.source_url for event in related]
        )
        if url
    }
    return ResearchPack(
        symbol=candidate.symbol,
        company_profile=f"{candidate.company} ({candidate.symbol})",
        what_changed=candidate.catalyst,
        why_now=candidate.next_confirmation,
        catalyst=candidate.catalyst,
        financial_quality=(
            f"Quality score {candidate.scores.quality:.1f}/100; "
            f"data confidence {candidate.scores.confidence:.0%}."
        ),
        earnings_revisions=(
            "Revision evidence is included in the deterministic strategy screen."
            if "earnings_revision_30d_pct" not in candidate.missing_fields
            else "Earnings revision evidence is missing."
        ),
        ownership_activity=(
            "Ownership activity requires an attached official filing or verified provider snapshot."
        ),
        valuation_summary=(
            f"Multi-model base {valuation.multi_model_fair_value.base:.2f}; "
            f"safety margin {valuation.safety_margin:.1%}."
            if valuation
            else "No reproducible valuation is attached."
        ),
        technical_context=(
            f"Timing score {candidate.scores.timing:.1f}/100; "
            f"confirmation: {candidate.next_confirmation}"
        ),
        news_context=[event.headline for event in related],
        thesis=candidate.catalyst,
        supporting_evidence=supporting,
        contrary_evidence=contrary,
        risks=risks,
        source_urls=sorted(urls),
        missing_information=missing,
        confidence=round(confidence, 3),
    )
