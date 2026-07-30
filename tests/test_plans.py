import pytest

from lmio.plans import ConditionalPlan, PlanState, transition


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
    confirmed = transition(watching, PlanState.CONFIRMED)

    assert confirmed.state is PlanState.CONFIRMED


def test_terminal_plan_cannot_restart() -> None:
    invalidated = transition(plan(), PlanState.INVALIDATED)

    with pytest.raises(ValueError, match="invalid plan transition"):
        transition(invalidated, PlanState.WATCHING)
