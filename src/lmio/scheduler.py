"""Canonical scheduler manifest and auditable job execution boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lmio.providers.sec import SECProvider
from lmio.sec_monitor import monitor_sec
from lmio.telegram import (
    MessageKind,
    drain_outbox,
    ensure_private_webhook,
    format_message,
    queue_or_send,
)

if TYPE_CHECKING:
    from lmio.service import LMIOService


MANIFEST_PATH = Path(__file__).parents[2] / "config" / "scheduler_manifest.json"


@dataclass(frozen=True, slots=True)
class Schedule:
    weekdays: tuple[int, ...]
    hour_utc: int
    minute_utc: int


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    job_id: str
    purpose: str
    command: str
    schedule: Schedule
    required_configuration: tuple[str, ...]


def load_scheduler_manifest(path: Path = MANIFEST_PATH) -> list[ScheduledJob]:
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported scheduler manifest schema")
    jobs = []
    for raw in payload["jobs"]:
        schedule = raw["schedule"]
        jobs.append(
            ScheduledJob(
                job_id=str(raw["id"]),
                purpose=str(raw["purpose"]),
                command=str(raw["command"]),
                schedule=Schedule(
                    weekdays=tuple(int(day) for day in schedule["weekdays"]),
                    hour_utc=int(schedule["hour_utc"]),
                    minute_utc=int(schedule["minute_utc"]),
                ),
                required_configuration=tuple(raw.get("requires", [])),
            )
        )
    identifiers = [job.job_id for job in jobs]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Scheduler job IDs must be unique")
    return jobs


def next_scheduled_time(job: ScheduledJob, after: datetime | None = None) -> datetime:
    current = (after or datetime.now(UTC)).astimezone(UTC)
    for offset in range(8):
        day = (current + timedelta(days=offset)).date()
        candidate = datetime(
            day.year,
            day.month,
            day.day,
            job.schedule.hour_utc,
            job.schedule.minute_utc,
            tzinfo=UTC,
        )
        if candidate.weekday() in job.schedule.weekdays and candidate > current:
            return candidate
    raise RuntimeError(f"No next schedule found for {job.job_id}")


def scheduled_window(job: ScheduledJob, at: datetime | None = None) -> datetime:
    """Return the most recent declared UTC slot for one overlap lock."""

    current = (at or datetime.now(UTC)).astimezone(UTC)
    for offset in range(8):
        day = (current - timedelta(days=offset)).date()
        candidate = datetime(
            day.year,
            day.month,
            day.day,
            job.schedule.hour_utc,
            job.schedule.minute_utc,
            tzinfo=UTC,
        )
        if candidate.weekday() in job.schedule.weekdays and candidate <= current:
            return candidate
    raise RuntimeError(f"No previous schedule found for {job.job_id}")


def scheduler_status(store: Any) -> dict[str, object]:
    jobs = load_scheduler_manifest()
    history = [
        item
        for item in store.history_json("system_events", 200)
        if item.get("event_type") == "scheduler_job"
    ]
    latest_by_job: dict[str, dict[str, Any]] = {}
    for item in history:
        job_id = str(dict(item.get("payload") or {}).get("job_id", ""))
        latest_by_job.setdefault(job_id, item)
    return {
        "manifest": str(MANIFEST_PATH.relative_to(Path(__file__).parents[2])),
        "manifest_loaded": True,
        "executor_process": "not_verified",
        "jobs": [
            {
                "id": job.job_id,
                "purpose": job.purpose,
                "command": job.command,
                "last_run": latest_by_job.get(job.job_id, {}).get("created_at"),
                "last_status": latest_by_job.get(job.job_id, {}).get("severity", "never_run"),
                "next_scheduled_time": next_scheduled_time(job).isoformat(),
            }
            for job in jobs
        ],
    }


def _execute(service: LMIOService, job_id: str) -> dict[str, object]:
    if job_id == "premarket-data-screening":
        return service.run_operational_pipeline()
    if job_id == "after-open-finviz-refresh":
        return service.refresh_finviz(message_kind=MessageKind.AFTER_OPEN)
    if job_id == "after-close-outcomes-report":
        outcomes = service.process_due_outcomes()
        performance = service.aggregate_strategy_performance()
        message = format_message(
            MessageKind.AFTER_CLOSE,
            regime="仅汇总已到期、具有实际价格证据的研究信号",
            opportunities=[
                f"本次完成 {outcomes['completed']} 个结果观察",
                f"更新 {performance['summaries']} 个策略/周期汇总",
            ],
            risks=[
                f"尚无可用价格证据 {outcomes['unavailable']} 项",
                f"处理失败 {outcomes['failed']} 项",
            ],
            next_actions=["等待未到期周期；未知值不会按零计算"],
        )
        report_id = service.store.append_json(
            "reports",
            {
                "report_type": "after_close_outcome_summary",
                "payload": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "message_zh": message,
                    "outcomes": outcomes,
                    "performance": performance,
                    "execution_capability": False,
                },
            },
        )
        delivery = queue_or_send(
            service.store,
            message,
            bot_token=service.settings.telegram_bot_token.get_secret_value(),
            chat_id=service.settings.telegram_chat_id.get_secret_value(),
            kind=MessageKind.AFTER_CLOSE,
            dedupe_context=f"after-close-report:{report_id}",
        )
        return {
            "status": "completed",
            "report_id": report_id,
            "outcomes": outcomes,
            "performance": performance,
            "telegram": delivery,
        }
    if job_id == "official-news-refresh":
        return service.refresh_official_news()
    if job_id == "sec-refresh":
        return monitor_sec(
            SECProvider(service.settings.sec_user_agent),
            service.store,
            service.settings.parsed_sec_watchlist(),
        )
    if job_id == "telegram-outbox-drain":
        return drain_outbox(
            service.store,
            bot_token=service.settings.telegram_bot_token.get_secret_value(),
            chat_id=service.settings.telegram_chat_id.get_secret_value(),
        )
    if job_id == "telegram-webhook-ensure":
        base_url = service.settings.public_base_url.strip().rstrip("/")
        if not base_url:
            raise RuntimeError("LMIO public base URL is not configured")
        return ensure_private_webhook(
            bot_token=service.settings.telegram_bot_token.get_secret_value(),
            webhook_secret=service.settings.telegram_webhook_secret.get_secret_value(),
            webhook_url=f"{base_url}/api/v1/telegram/webhook",
        )
    if job_id == "weekend-strategy-data-quality-review":
        from lmio.health_console import build_system_health

        return {
            "status": "completed",
            "health": build_system_health(service.store, service.settings),
            "strategy_performance_records": service.store.counts()["strategy_performance"],
        }
    raise ValueError(f"Unknown scheduler job: {job_id}")


def run_scheduled_job(
    service: LMIOService,
    job_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    jobs = {job.job_id: job for job in load_scheduler_manifest()}
    if job_id not in jobs:
        raise ValueError(f"Job is not declared in scheduler manifest: {job_id}")
    started = (now or datetime.now(UTC)).astimezone(UTC)
    window = scheduled_window(jobs[job_id], started)
    lock_key = f"scheduler:{job_id}:{window.isoformat()}"
    acquired = service.store.mark_ingestion_fingerprint(lock_key, "scheduler_window")
    if not acquired:
        finished = datetime.now(UTC)
        service.store.append_json(
            "system_events",
            {
                "event_type": "scheduler_job",
                "severity": "skipped_duplicate",
                "payload": {
                    "job_id": job_id,
                    "scheduled_time": window.isoformat(),
                    "started_at": started.isoformat(),
                    "finished_at": finished.isoformat(),
                    "lock_key": lock_key,
                    "lock_acquired": False,
                    "skipped_duplicate": True,
                },
            },
        )
        return {
            "job_id": job_id,
            "status": "skipped_duplicate",
            "scheduled_time": window.isoformat(),
        }
    try:
        result = _execute(service, job_id)
    except Exception as error:
        service.store.append_json(
            "system_events",
            {
                "event_type": "scheduler_job",
                "severity": "failed",
                "payload": {
                    "job_id": job_id,
                    "scheduled_time": window.isoformat(),
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "lock_key": lock_key,
                    "lock_acquired": True,
                    "error_category": type(error).__name__,
                },
            },
        )
        raise
    finished = datetime.now(UTC)
    status = str(result.get("status", "completed"))
    severity = "succeeded" if status in {"completed", "succeeded", "ok"} else status
    service.store.append_json(
        "system_events",
        {
            "event_type": "scheduler_job",
            "severity": severity,
            "payload": {
                "job_id": job_id,
                "scheduled_time": window.isoformat(),
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "run_id": result.get("run_id"),
                "lock_key": lock_key,
                "lock_acquired": True,
                "skipped_duplicate": False,
                "duration_ms": int((finished - started).total_seconds() * 1000),
                "next_scheduled_time": next_scheduled_time(jobs[job_id], finished).isoformat(),
            },
        },
    )
    return {"job_id": job_id, "status": severity, "result": result}
