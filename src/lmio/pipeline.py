"""One evidence-bearing, fail-closed operational pipeline for LMIO."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class StageResult(BaseModel):
    status: StageStatus = StageStatus.SUCCEEDED
    output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    error_summary: str | None = None
    evidence_references: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class PipelineStage(BaseModel):
    run_id: str
    stage_order: int
    stage_name: str
    status: StageStatus
    started_at: datetime
    finished_at: datetime
    input_count: int = Field(default=0, ge=0)
    output_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    error_summary: str | None = None
    evidence_references: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


STAGE_NAMES = (
    "provider_preflight",
    "finviz_market_snapshot",
    "official_macro_news_refresh",
    "sec_filing_and_ownership_refresh",
    "investable_universe",
    "independent_strategy_screens",
    "pattern_recognition",
    "four_dimension_scoring",
    "top_10_generation",
    "valuation_input_preparation",
    "valuation_and_applicability_routing",
    "top_3_preliminary_eligibility",
    "fifteen_field_research_package",
    "news_price_confirmation",
    "candidate_and_conditional_plan_updates",
    "chinese_daily_brief",
    "telegram_queue_and_delivery",
    "signal_eligibility_check",
    "due_outcome_updates",
    "strategy_performance_aggregation",
    "health_summary",
)

# Failure of current market data makes analytical output misleading. Other
# stages may degrade the run but leave explicitly marked partial evidence.
CRITICAL_STAGE_ORDERS = {1, 2, 5, 6, 8, 9, 16}
ALWAYS_RUN_STAGE_ORDERS = {21}

StageHandler = Callable[[dict[str, Any]], StageResult]


class OperationalPipeline:
    """Execute one canonical run and persist every truthful stage outcome."""

    def __init__(self, store: Any, handlers: dict[int, StageHandler]) -> None:
        self.store = store
        self.handlers = handlers

    def run(self, *, initial_context: dict[str, Any] | None = None) -> dict[str, Any]:
        run_id = f"lmio-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
        context: dict[str, Any] = {"run_id": run_id, **(initial_context or {})}
        started_at = datetime.now(UTC)
        stages: list[PipelineStage] = []
        blocking_stage: int | None = None

        for order, name in enumerate(STAGE_NAMES, start=1):
            stage_started = datetime.now(UTC)
            input_count = _count_context(context)
            if blocking_stage is not None and order not in ALWAYS_RUN_STAGE_ORDERS:
                result = StageResult(
                    status=StageStatus.BLOCKED,
                    error_summary=f"Blocked by critical stage {blocking_stage:02d}.",
                    evidence_references=[f"pipeline:{run_id}:stage:{blocking_stage:02d}"],
                )
            else:
                handler = self.handlers.get(order)
                if handler is None:
                    result = StageResult(
                        status=StageStatus.SKIPPED,
                        warning_count=1,
                        error_summary="No operational handler is configured.",
                    )
                else:
                    try:
                        result = handler(context)
                    except Exception as error:  # fail closed; retain only safe class name
                        result = StageResult(
                            status=StageStatus.FAILED,
                            error_summary=type(error).__name__,
                        )
            finished_at = datetime.now(UTC)
            stage = PipelineStage(
                run_id=run_id,
                stage_order=order,
                stage_name=name,
                status=result.status,
                started_at=stage_started,
                finished_at=finished_at,
                input_count=input_count,
                output_count=result.output_count,
                warning_count=result.warning_count,
                error_count=1 if result.status is StageStatus.FAILED else 0,
                retry_count=result.retry_count,
                error_summary=result.error_summary,
                evidence_references=result.evidence_references,
                details=result.details,
            )
            stages.append(stage)
            if result.status is StageStatus.FAILED and order in CRITICAL_STAGE_ORDERS:
                blocking_stage = order

        run_status = _run_status(stages)
        finished_at = datetime.now(UTC)
        payload = {
            "run_id": run_id,
            "status": run_status,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
            "blocking_stage": blocking_stage,
            "stage_counts": {
                status.value: sum(stage.status is status for stage in stages)
                for status in StageStatus
            },
        }
        # Persist the parent first so local foreign keys are satisfied, then
        # immutable final evidence for every stage.
        self.store.append_json(
            "pipeline_runs", {"run_id": run_id, "status": run_status, "payload": payload}
        )
        for stage in stages:
            self.store.append_json(
                "pipeline_stages",
                {
                    "run_id": run_id,
                    "stage_order": stage.stage_order,
                    "stage_name": stage.stage_name,
                    "status": stage.status,
                    "payload": stage.model_dump(mode="json"),
                },
            )
        return {**payload, "stages": [stage.model_dump(mode="json") for stage in stages]}


def _count_context(context: dict[str, Any]) -> int:
    for key in ("snapshots", "candidates", "top_10", "research_packs"):
        value = context.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _run_status(stages: list[PipelineStage]) -> str:
    if any(stage.status is StageStatus.FAILED for stage in stages):
        return StageStatus.FAILED
    if any(stage.status in {StageStatus.PARTIAL, StageStatus.BLOCKED} for stage in stages):
        return StageStatus.PARTIAL
    return StageStatus.SUCCEEDED
