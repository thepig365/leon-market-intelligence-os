"""Conditional research plan state machine; never an order-execution path."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PlanState(StrEnum):
    DRAFT = "draft"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PLAN_READY = "plan_ready"
    MONITORING = "monitoring"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    ARCHIVED = "archived"

    # Compatibility aliases used by foundation records.
    WATCHING = "waiting_confirmation"
    CONFIRMED = "plan_ready"
    CLOSED = "expired"
    REVIEWED = "archived"


ALLOWED_TRANSITIONS = {
    PlanState.DRAFT: {PlanState.WAITING_CONFIRMATION, PlanState.INVALIDATED},
    PlanState.WAITING_CONFIRMATION: {PlanState.PLAN_READY, PlanState.INVALIDATED},
    PlanState.PLAN_READY: {PlanState.MONITORING, PlanState.INVALIDATED},
    PlanState.MONITORING: {PlanState.EXPIRED, PlanState.INVALIDATED},
    PlanState.INVALIDATED: {PlanState.ARCHIVED},
    PlanState.EXPIRED: {PlanState.ARCHIVED},
    PlanState.ARCHIVED: set(),
}


class ConditionalPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    state: PlanState = PlanState.DRAFT
    thesis: str
    confirmation_condition: str
    risk_condition: str = "Risk conditions require authenticated operator review."
    invalidation_condition: str
    entry_zone: str
    stop_reference: str
    target_reference: str
    risk_reward: float = Field(gt=0)
    evidence_urls: list[str]
    market_snapshot_references: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    created_by: str = "lmio-system"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: str = "conditional-plan-v1"


class PlanTransition(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    previous_state: PlanState
    new_state: PlanState
    actor: str
    reason: str
    evidence_urls: list[str]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def transition_with_evidence(
    plan: ConditionalPlan,
    target: PlanState,
    *,
    actor: str,
    reason: str,
    evidence_urls: list[str],
) -> tuple[ConditionalPlan, PlanTransition]:
    if target not in ALLOWED_TRANSITIONS[plan.state]:
        raise ValueError(f"invalid plan transition: {plan.state} -> {target}")
    if not actor.strip() or not reason.strip():
        raise ValueError("actor and reason are required")
    updated = plan.model_copy(update={"state": target})
    event = PlanTransition(
        symbol=plan.symbol,
        previous_state=plan.state,
        new_state=target,
        actor=actor,
        reason=reason,
        evidence_urls=evidence_urls,
    )
    return updated, event


def transition(plan: ConditionalPlan, target: PlanState) -> ConditionalPlan:
    """Compatibility helper for non-paper foundation transitions."""
    updated, _ = transition_with_evidence(
        plan,
        target,
        actor="lmio-system",
        reason="foundation compatibility transition",
        evidence_urls=plan.evidence_urls,
    )
    return updated
