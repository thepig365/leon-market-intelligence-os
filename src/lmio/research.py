"""Structured 15-field evidence packs without unsupported AI invention."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from lmio.domain import DataProvenance, NewsEvent, ScreenCandidate, ValuationResult
from lmio.news import news_impact_score


class StatementClass(StrEnum):
    VERIFIED_FACT = "verified_fact"
    CALCULATED_FACT = "calculated_fact"
    MODEL_INFERENCE = "model_inference"
    ANALYST_JUDGMENT = "analyst_judgment"
    MISSING = "missing"


class ResearchStatement(BaseModel):
    text: str
    classification: StatementClass
    evidence_references: list[str] = Field(default_factory=list)


class ResearchPack(BaseModel):
    symbol: str
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE
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
    fields: dict[str, list[ResearchStatement]] = Field(default_factory=dict)
    model_provider: str = "lmio-deterministic"
    prompt_template_version: str = "research-15-fields-v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_snapshot_ids: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    news_price_confirmation: dict[str, object] = Field(default_factory=dict)


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
    evidence_refs = sorted(urls) or [f"provider:{candidate.symbol}:screen-snapshot"]

    def statement(
        text: str,
        classification: StatementClass,
        *,
        evidence: list[str] | None = None,
    ) -> ResearchStatement:
        references = evidence or []
        if classification in {StatementClass.VERIFIED_FACT, StatementClass.CALCULATED_FACT}:
            references = references or evidence_refs
        return ResearchStatement(
            text=text,
            classification=classification,
            evidence_references=references,
        )

    missing_statement = lambda topic: statement(  # noqa: E731
        f"{topic} evidence has not been attached.", StatementClass.MISSING
    )
    fields: dict[str, list[ResearchStatement]] = {
        "business_model": [missing_statement("Business model")],
        "revenue_structure": [missing_statement("Revenue structure")],
        "industry_position": [missing_statement("Industry position")],
        "competitive_advantage": [missing_statement("Competitive advantage")],
        "management_and_capital_allocation": [
            missing_statement("Management and capital allocation")
        ],
        "financial_quality": [
            statement(
                f"Quality score {candidate.scores.quality:.1f}/100.",
                StatementClass.CALCULATED_FACT,
            )
        ],
        "growth_drivers": [statement(candidate.catalyst, StatementClass.MODEL_INFERENCE)],
        "earnings_revisions": [
            (
                statement(
                    "Revision inputs were included in the approved deterministic screen.",
                    StatementClass.CALCULATED_FACT,
                )
                if "earnings_revision_30d_pct" not in candidate.missing_fields
                else missing_statement("Earnings revision")
            )
        ],
        "institutional_ownership": [missing_statement("Institutional ownership")],
        "insider_activity": [missing_statement("Insider activity")],
        "valuation": [
            (
                statement(
                    f"Multi-model base {valuation.multi_model_fair_value.base:.2f}; "
                    f"safety margin {valuation.safety_margin:.1%}.",
                    StatementClass.CALCULATED_FACT,
                )
                if valuation
                else missing_statement("Reproducible valuation")
            )
        ],
        "catalysts": [statement(candidate.catalyst, StatementClass.MODEL_INFERENCE)],
        "risks": [statement(risk, StatementClass.ANALYST_JUDGMENT) for risk in risks],
        "bear_case_and_contrary_evidence": [
            statement(item, StatementClass.VERIFIED_FACT, evidence=evidence_refs)
            for item in contrary
        ]
        or [missing_statement("Contrary evidence")],
        "conditional_plan_and_invalidation": [
            statement(candidate.next_confirmation, StatementClass.ANALYST_JUDGMENT),
            statement(candidate.invalidation, StatementClass.ANALYST_JUDGMENT),
        ],
    }
    return ResearchPack(
        symbol=candidate.symbol,
        provenance=candidate.provenance,
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
        fields=fields,
        source_snapshot_ids=evidence_refs,
        invalidation_conditions=[candidate.invalidation],
        news_price_confirmation={
            "state": "pending" if related else "unavailable",
            "reason": (
                "Price windows require stored post-event market snapshots."
                if related
                else "No symbol-linked event is available."
            ),
        },
    )
