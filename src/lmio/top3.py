"""Deterministic Top 3 evidence gates and structured blocking explanations."""

from collections import Counter

from lmio.domain import (
    DataProvenance,
    ScreenCandidate,
    Top3EligibilityState,
    Top3Evaluation,
    Top3Status,
    ValuationResult,
)
from lmio.research import ResearchPack


def evaluate_top3(
    candidates: list[ScreenCandidate],
    valuations: dict[str, ValuationResult],
    research_packs: dict[str, ResearchPack],
) -> tuple[list[ScreenCandidate], Top3Status]:
    """Select at most three candidates only after every evidence gate is evaluated."""

    evaluations: list[Top3Evaluation] = []
    eligible: list[ScreenCandidate] = []
    for candidate in candidates[:10]:
        valuation = valuations.get(candidate.symbol)
        research = research_packs.get(candidate.symbol)
        blocked: list[str] = []
        state = Top3EligibilityState.SCREENED
        valuation_applicability = "not_evaluated"
        research_completeness = 0.0

        if candidate.provenance in {
            DataProvenance.SYNTHETIC_REPLAY,
            DataProvenance.TEST_FIXTURE,
        }:
            blocked.append("non-operational provenance")
            state = Top3EligibilityState.REJECTED
        elif valuation is None:
            blocked.append("missing authorised valuation inputs")
            state = Top3EligibilityState.VALUATION_PENDING
        elif valuation.provenance is not candidate.provenance:
            blocked.append("valuation provenance does not match market evidence")
            state = Top3EligibilityState.REJECTED
            valuation_applicability = "provenance_mismatch"
        else:
            valuation_applicability = "applicable"

        if research is None:
            blocked.append("15-field research package is pending")
            if state is Top3EligibilityState.SCREENED:
                state = Top3EligibilityState.RESEARCH_PENDING
        else:
            research_completeness = research.mandatory_completion
            if research.provenance is not candidate.provenance:
                blocked.append("research provenance does not match market evidence")
                state = Top3EligibilityState.REJECTED
            elif research_completeness < 1:
                blocked.append("research evidence is incomplete")
                if state not in {
                    Top3EligibilityState.REJECTED,
                    Top3EligibilityState.VALUATION_PENDING,
                }:
                    state = Top3EligibilityState.EVIDENCE_INCOMPLETE

        if candidate.missing_fields:
            blocked.append("required screening fields are missing")
            if state not in {Top3EligibilityState.REJECTED, Top3EligibilityState.VALUATION_PENDING}:
                state = Top3EligibilityState.EVIDENCE_INCOMPLETE
        if candidate.scores.confidence < 0.75:
            blocked.append("data confidence below 75%")
            if state not in {Top3EligibilityState.REJECTED, Top3EligibilityState.VALUATION_PENDING}:
                state = Top3EligibilityState.EVIDENCE_INCOMPLETE
        if candidate.source_completeness < 0.75:
            blocked.append("source completeness below 75%")
            if state not in {Top3EligibilityState.REJECTED, Top3EligibilityState.VALUATION_PENDING}:
                state = Top3EligibilityState.EVIDENCE_INCOMPLETE

        if not blocked:
            state = Top3EligibilityState.TOP3_ELIGIBLE
            eligible.append(candidate)
        evaluations.append(
            Top3Evaluation(
                symbol=candidate.symbol,
                strategy=candidate.strategy,
                state=state,
                strategy_match=True,
                scores=candidate.scores,
                data_confidence=candidate.scores.confidence,
                source_completeness=candidate.source_completeness,
                valuation_applicability=valuation_applicability,
                research_completeness=research_completeness,
                catalyst=candidate.catalyst,
                supporting_evidence=(
                    research.supporting_evidence
                    if research is not None
                    else [item.summary for item in candidate.evidence]
                ),
                contrary_evidence=(research.contrary_evidence if research is not None else []),
                next_confirmation=candidate.next_confirmation,
                invalidation_conditions=candidate.invalidation,
                blocked_reasons=blocked,
            )
        )

    selected = eligible[:3]
    selected_keys = {(item.symbol, item.strategy) for item in selected}
    evaluations = [
        item.model_copy(update={"state": Top3EligibilityState.TOP3_SELECTED})
        if (item.symbol, item.strategy) in selected_keys
        else item
        for item in evaluations
    ]
    counts = Counter(reason for item in evaluations for reason in item.blocked_reasons)
    actions: list[str] = []
    if counts.get("missing authorised valuation inputs"):
        actions.append("refresh authorised financial evidence and build valuation inputs")
    if counts.get("15-field research package is pending") or counts.get(
        "research evidence is incomplete"
    ):
        actions.append("complete the evidence-linked 15-field research package")
    if counts.get("required screening fields are missing") or counts.get(
        "source completeness below 75%"
    ):
        actions.append("refresh the authorised provider snapshot")

    return selected, Top3Status(
        available=bool(selected),
        message=(
            f"Top 3 available: {len(selected)} candidate(s) passed all gates."
            if selected
            else "Top 3 unavailable: no candidate passed all evidence gates."
        ),
        reason_counts=dict(counts),
        next_required_actions=actions,
        evaluations=evaluations,
    )
