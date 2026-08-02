from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from lmio.config import Settings
from lmio.scheduler import (
    load_scheduler_manifest,
    next_scheduled_time,
    run_scheduled_job,
    scheduler_status,
)
from lmio.service import LMIOService
from lmio.telegram import MessageKind


def test_weekend_job_executes_and_persists_truthful_history(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = run_scheduled_job(service, "weekend-strategy-data-quality-review")
    status = scheduler_status(service.store)

    assert result["status"] == "succeeded"
    weekend = next(
        item for item in status["jobs"] if item["id"] == "weekend-strategy-data-quality-review"
    )
    assert weekend["last_status"] == "succeeded"
    assert weekend["last_run"] is not None


def test_scheduler_prevents_overlapping_runs_in_same_window(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    now = datetime(2026, 8, 1, 15, tzinfo=UTC)

    first = run_scheduled_job(service, "weekend-strategy-data-quality-review", now=now)
    second = run_scheduled_job(service, "weekend-strategy-data-quality-review", now=now)

    assert first["status"] == "succeeded"
    assert second["status"] == "skipped_duplicate"
    event = service.store.history_json("system_events", 1)[0]
    assert event["payload"]["lock_acquired"] is False
    assert event["payload"]["skipped_duplicate"] is True


def test_scheduler_keeps_declared_utc_slot_across_melbourne_daylight_saving() -> None:
    job = next(
        item for item in load_scheduler_manifest() if item.job_id == "premarket-data-screening"
    )
    melbourne = ZoneInfo("Australia/Melbourne")

    standard_time_result = next_scheduled_time(
        job,
        datetime(2026, 7, 6, 8, tzinfo=melbourne),
    )
    daylight_time_result = next_scheduled_time(
        job,
        datetime(2026, 12, 7, 8, tzinfo=melbourne),
    )

    assert standard_time_result.tzinfo is UTC
    assert daylight_time_result.tzinfo is UTC
    assert (standard_time_result.hour, standard_time_result.minute) == (12, 0)
    assert (daylight_time_result.hour, daylight_time_result.minute) == (12, 0)


def test_after_open_job_truthfully_runs_only_authorised_finviz_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    calls: list[MessageKind] = []

    def fake_refresh(
        _service: LMIOService,
        *,
        message_kind: MessageKind,
    ) -> dict[str, object]:
        calls.append(message_kind)
        return {"status": "completed", "run_id": "finviz-after-open"}

    monkeypatch.setattr(LMIOService, "refresh_finviz", fake_refresh)
    result = run_scheduled_job(
        service,
        "after-open-finviz-refresh",
        now=datetime(2026, 8, 3, 16, tzinfo=UTC),
    )

    assert result["status"] == "succeeded"
    assert calls == [MessageKind.AFTER_OPEN]


def test_after_close_job_stores_report_and_queues_delivery(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = run_scheduled_job(
        service,
        "after-close-outcomes-report",
        now=datetime(2026, 8, 3, 22, tzinfo=UTC),
    )

    assert result["status"] == "succeeded"
    payload = result["result"]
    assert payload["outcomes"]["completed"] == 0
    assert payload["performance"]["summaries"] == 0
    assert payload["telegram"] == "queued_not_configured"
    report = service.store.history_json("reports", 1)[0]
    assert report["report_type"] == "after_close_outcome_summary"
    assert report["payload"]["execution_capability"] is False


def test_telegram_webhook_job_uses_protected_runtime_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        TELEGRAM_BOT_TOKEN="123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        TELEGRAM_WEBHOOK_SECRET="private-webhook-secret",
        LMIO_PUBLIC_BASE_URL="https://runtime.example/",
    )
    service = LMIOService(settings)
    captured: dict[str, str] = {}

    def fake_ensure(**kwargs: str) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "ready", "webhook_configured": True}

    monkeypatch.setattr("lmio.scheduler.ensure_private_webhook", fake_ensure)
    result = run_scheduled_job(
        service,
        "telegram-webhook-ensure",
        now=datetime(2026, 8, 3, 1, tzinfo=UTC),
    )

    assert result["status"] == "ready"
    assert captured["webhook_url"] == "https://runtime.example/api/v1/telegram/webhook"


def test_failed_scheduler_job_records_auditable_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    def fail_performance(_service: LMIOService) -> dict[str, int]:
        raise RuntimeError("deliberate scheduler test failure")

    monkeypatch.setattr(LMIOService, "aggregate_strategy_performance", fail_performance)

    with pytest.raises(RuntimeError, match="deliberate scheduler test failure"):
        run_scheduled_job(
            service,
            "after-close-outcomes-report",
            now=datetime(2026, 8, 4, 22, tzinfo=UTC),
        )

    event = service.store.history_json("system_events", 1)[0]
    assert event["severity"] == "failed"
    assert event["payload"]["lock_acquired"] is True
    assert event["payload"]["error_category"] == "RuntimeError"
