"""Conditional research plan state machine; never an order-execution path."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PlanState(StrEnum):
    DRAFT = "draft"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PAPER_READY = "paper_ready"
    PAPER_OPEN = "paper_open"
    INVALIDATED = "invalidated"
    CLOSED = "closed"
    REVIEWED = "reviewed"

    # Compatibility aliases used by foundation records.
    WATCHING = "waiting_confirmation"
    CONFIRMED = "paper_ready"
    EXPIRED = "closed"


ALLOWED_TRANSITIONS = {
    PlanState.DRAFT: {PlanState.WAITING_CONFIRMATION, PlanState.INVALIDATED},
    PlanState.WAITING_CONFIRMATION: {PlanState.PAPER_READY, PlanState.INVALIDATED},
    PlanState.PAPER_READY: {PlanState.PAPER_OPEN, PlanState.INVALIDATED},
    PlanState.PAPER_OPEN: {PlanState.CLOSED, PlanState.INVALIDATED},
    PlanState.INVALIDATED: {PlanState.REVIEWED},
    PlanState.CLOSED: {PlanState.REVIEWED},
    PlanState.REVIEWED: set(),
}


class ConditionalPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    state: PlanState = PlanState.DRAFT
    thesis: str
    confirmation_condition: str
    invalidation_condition: str
    entry_zone: str
    stop_reference: str
    target_reference: str
    risk_reward: float = Field(gt=0)
    evidence_urls: list[str]
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
    paper_trading_enabled: bool = False,
) -> tuple[ConditionalPlan, PlanTransition]:
    if target not in ALLOWED_TRANSITIONS[plan.state]:
        raise ValueError(f"invalid plan transition: {plan.state} -> {target}")
    if target in {PlanState.PAPER_READY, PlanState.PAPER_OPEN} and not paper_trading_enabled:
        raise PermissionError("paper trading is disabled")
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
        paper_trading_enabled=False,
    )
    return updated
