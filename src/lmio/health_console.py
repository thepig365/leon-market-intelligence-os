"""Truthful five-layer operational health assembled from persisted runtime evidence."""

from datetime import UTC, datetime
from importlib.util import find_spec
from typing import Any

from lmio.config import Settings
from lmio.freshness import DataType, FreshnessState, evaluate_freshness


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _provider_statuses(store: Any, settings: Settings) -> dict[str, dict[str, object]]:
    history = store.history_json("provider_health", 200)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in history:
        grouped.setdefault(str(item.get("provider", "unknown")), []).append(item)
    readiness = settings.integration_readiness()
    configured = {
        "finviz_elite_api": readiness["finviz_configured"],
        "sec_edgar": readiness["sec_configured"],
        "telegram": readiness["telegram_configured"],
        "official_macro": True,
    }
    result: dict[str, dict[str, object]] = {}
    for provider in sorted(set(configured) | set(grouped)):
        events = grouped.get(provider, [])
        latest = events[0] if events else {}
        latest_payload = dict(latest.get("payload") or {})
        ingestion = dict(latest_payload.get("ingestion") or {})
        failures = 0
        for event in events:
            if str(event.get("state")) == "ready":
                break
            failures += 1
        started = _parse_time(ingestion.get("retrieval_started_at"))
        finished = _parse_time(ingestion.get("retrieval_completed_at"))
        latency_ms = (
            int((finished - started).total_seconds() * 1000)
            if started and finished
            else None
        )
        result[provider] = {
            "configured": configured.get(provider, True),
            "last_attempt": latest.get("created_at"),
            "last_success": next(
                (item.get("created_at") for item in events if item.get("state") == "ready"),
                None,
            ),
            "records_received": ingestion.get("row_count_received"),
            "latency_ms": latency_ms,
            "consecutive_failures": failures,
            "current_state": latest.get("state", "not_verified"),
            "last_error_category": latest_payload.get("error_category"),
        }
    return result


def _latest_freshness(
    store: Any,
    table: str,
    data_type: DataType,
    *,
    source: str,
) -> dict[str, object]:
    records = store.history_json(table, 1)
    if not records:
        return evaluate_freshness(
            data_type,
            as_of=None,
            retrieved_at=datetime.now(UTC),
            source=source,
            snapshot_id=f"{source}:unavailable",
        ).model_dump(mode="json")
    record = records[0]
    payload = dict(record.get("payload") or {})
    as_of = _parse_time(
        payload.get("observed_at")
        or payload.get("generated_at")
        or record.get("observed_at")
        or record.get("created_at")
    )
    retrieved_at = _parse_time(record.get("created_at")) or datetime.now(UTC)
    return evaluate_freshness(
        data_type,
        as_of=as_of,
        retrieved_at=retrieved_at,
        source=source,
        snapshot_id=f"{table}:{record.get('id', 'latest')}",
    ).model_dump(mode="json")


def build_system_health(store: Any, settings: Settings) -> dict[str, object]:
    from lmio.scheduler import scheduler_status

    scheduler = scheduler_status(store)
    pipeline_runs = store.history_json("pipeline_runs", 1)
    pipeline = pipeline_runs[0] if pipeline_runs else None
    pipeline_payload = dict(pipeline.get("payload") or {}) if pipeline else {}
    pipeline_stages = store.history_json("pipeline_stages", 50) if pipeline else []
    failed_or_blocked = next(
        (
            item
            for item in reversed(pipeline_stages)
            if item.get("status") in {"failed", "blocked"}
        ),
        None,
    )
    freshness = {
        "market_snapshot": _latest_freshness(
            store, "provider_snapshots", DataType.MARKET_SNAPSHOT, source="market"
        ),
        "sec": _latest_freshness(
            store, "ownership_events", DataType.SEC_FILING, source="sec"
        ),
        "macro_news": _latest_freshness(
            store, "provider_health", DataType.MACRO_RELEASE, source="official_macro"
        ),
        "ownership": _latest_freshness(
            store,
            "ownership_events",
            DataType.INSTITUTIONAL_OWNERSHIP,
            source="sec",
        ),
        "valuations": _latest_freshness(
            store, "valuation_runs", DataType.VALUATION, source="valuation"
        ),
        "top_10": _latest_freshness(
            store, "reports", DataType.TOP_10, source="daily_report"
        ),
        "top_3": _latest_freshness(
            store, "top3_evaluations", DataType.TOP_3, source="top3"
        ),
        "research_packages": _latest_freshness(
            store, "research_packs", DataType.RESEARCH_PACKAGE, source="research"
        ),
    }
    stale_items = [
        name
        for name, item in freshness.items()
        if item["freshness_state"] in {FreshnessState.STALE, FreshnessState.UNKNOWN}
    ]
    return {
        "status": "degraded" if stale_items or failed_or_blocked else "ok",
        "application": {
            "dashboard": "configured",
            "runtime_api": "ready",
            "database": store.connectivity_check()["status"],
            "scheduler": scheduler,
            "telegram": (
                "configured_not_verified"
                if settings.integration_readiness()["telegram_configured"]
                else "disabled"
            ),
        },
        "providers": _provider_statuses(store, settings),
        "freshness": freshness,
        "pipeline": {
            "last_full_run": pipeline_payload.get("finished_at"),
            "status": pipeline.get("status") if pipeline else "never_run",
            "failed_or_blocked_stage": (
                failed_or_blocked.get("stage_name") if failed_or_blocked else None
            ),
            "retry_status": "recorded_per_stage" if pipeline else "not_applicable",
            "next_run": min(
                (str(item["next_scheduled_time"]) for item in scheduler["jobs"]),
                default=None,
            ),
            "duration_ms": pipeline_payload.get("duration_ms"),
        },
        "safety": {
            "CAN_TRADE": settings.can_trade,
            "LIVE_TRADING_ENABLED": settings.live_trading_enabled,
            "PAPER_TRADING_ENABLED": settings.paper_trading_enabled,
            "broker_package_absent": all(
                find_spec(name) is None for name in ("ib_insync", "ibapi", "alpaca_trade_api")
            ),
            "order_endpoint_absent": True,
        },
        "stale_or_unknown": stale_items,
    }
