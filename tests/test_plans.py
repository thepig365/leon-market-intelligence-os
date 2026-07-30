import pytest

from lmio.plans import (
    ConditionalPlan,
    PlanState,
    transition,
    transition_with_evidence,
)


def plan() -> ConditionalPlan:
    return ConditionalPlan(
        symbol="TEST",
        thesis="Official evidence indicates a material change.",
        confirmation_condition="Price and volume confirm after the event.",
        invalidation_condition="Official guidance reverses or price fails support.",
        entry_zone="Research reference only",
        stop_reference="Deterministic support reference",
        target_reference="Prior resistance reference",
        risk_reward=2,
        evidence_urls=["https://www.sec.gov/example"],
    )


def test_valid_plan_transitions_are_explicit() -> None:
    watching = transition(plan(), PlanState.WATCHING)

    assert watching.state is PlanState.WAITING_CONFIRMATION

    with pytest.raises(PermissionError, match="paper trading is disabled"):
        transition(watching, PlanState.CONFIRMED)


def test_transition_records_actor_reason_and_evidence() -> None:
    updated, event = transition_with_evidence(
        plan(),
        PlanState.WAITING_CONFIRMATION,
        actor="research-agent",
        reason="Official filing requires price confirmation.",
        evidence_urls=["https://www.sec.gov/example"],
    )

    assert updated.state is PlanState.WAITING_CONFIRMATION
    assert event.previous_state is PlanState.DRAFT
    assert event.actor == "research-agent"


def test_terminal_plan_cannot_restart() -> None:
    invalidated = transition(plan(), PlanState.INVALIDATED)

    with pytest.raises(ValueError, match="invalid plan transition"):
        transition(invalidated, PlanState.WATCHING)
