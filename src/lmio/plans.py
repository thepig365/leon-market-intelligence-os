"""Conditional research plan state machine; never an order-execution path."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PlanState(StrEnum):
    DRAFT = "draft"
    WATCHING = "watching"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


ALLOWED_TRANSITIONS = {
    PlanState.DRAFT: {PlanState.WATCHING, PlanState.INVALIDATED},
    PlanState.WATCHING: {PlanState.CONFIRMED, PlanState.INVALIDATED, PlanState.EXPIRED},
    PlanState.CONFIRMED: {PlanState.INVALIDATED, PlanState.EXPIRED},
    PlanState.INVALIDATED: set(),
    PlanState.EXPIRED: set(),
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


def transition(plan: ConditionalPlan, target: PlanState) -> ConditionalPlan:
    if target not in ALLOWED_TRANSITIONS[plan.state]:
        raise ValueError(f"invalid plan transition: {plan.state} -> {target}")
    return plan.model_copy(update={"state": target})
