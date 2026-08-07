"""LMIO FastAPI application and local read-only command centre."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from html import escape
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from lmio import __version__
from lmio.audit import audit_event
from lmio.config import get_settings
from lmio.domain import NewsEvent
from lmio.health_console import build_system_health
from lmio.ibkr_bridge import IBKRBridgeHeartbeat
from lmio.news import news_impact_score
from lmio.news_plan import propose_news_plan
from lmio.news_price import ConfirmationState, NewsPriceConfirmation
from lmio.news_research import build_news_research_board
from lmio.options import (
    OptionBatch,
    format_option_alert,
    parse_barchart_csv,
    persisted_option,
)
from lmio.options_screenshot import validate_options_screenshot_data_url
from lmio.plans import ConditionalPlan, PlanState, transition_with_evidence
from lmio.roles import Principal
from lmio.scheduler import run_scheduled_job, scheduler_status
from lmio.security import (
    require_admin,
    require_cron,
    require_dashboard_refresh,
    require_ibkr_bridge,
    require_telegram_webhook,
    valid_cron_credential,
    valid_read_credential,
)
from lmio.service import LMIOService
from lmio.telegram import (
    MessageKind,
    drain_outbox,
    format_symbol_research,
    parse_symbol_query,
    queue_or_send,
)

app = FastAPI(
    title="Leon Market Intelligence OS",
    description="Evidence-backed United States equity research and decision support",
    version=__version__,
)

DASHBOARD_PAGES = {
    "command-centre": "指挥中心",
    "top-10": "今日 Top 10",
    "strategy-screener": "策略筛选",
    "news-trading": "新闻研究",
    "institutional-insider": "机构与内部人",
    "intrinsic-value": "内在价值",
    "watchlists": "观察名单",
    "conditional-plans": "条件计划",
    "reports-journal": "报告与日志",
    "system-health": "系统健康",
    "settings": "设置",
    "unusual-options": "Options Trading / 期权研究",
    "paper-trades": "模拟交易（关闭）",
}


@app.middleware("http")
async def require_runtime_read_key(request: Request, call_next: Any) -> Response:
    """Keep runtime evidence private while leaving a minimal health probe."""

    read_allowed = valid_read_credential(request.headers.get("x-lmio-read-key"))
    cron_path = request.url.path in {
        "/api/v1/providers/finviz/refresh",
        "/api/v1/providers/news/refresh",
    } or request.url.path.startswith("/api/v1/scheduler/")
    cron_allowed = cron_path and valid_cron_credential(
        request.headers.get("authorization"), request.headers.get("x-lmio-cron-key")
    )
    webhook_path = request.url.path == "/api/v1/telegram/webhook"
    bridge_path = request.url.path in {
        "/api/v1/providers/ibkr/heartbeat",
        "/api/v1/providers/ibkr/options",
    }
    if (
        request.url.path not in {"/health", "/favicon.ico"}
        and not webhook_path
        and not bridge_path
        and not (read_allowed or cron_allowed)
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid LMIO runtime read credential."},
        )
    return await call_next(request)


@lru_cache
def get_service() -> LMIOService:
    return LMIOService(get_settings())


def health_payload() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "Leon Market Intelligence OS",
        "version": __version__,
        **settings.public_health(),
    }


@app.get("/health", tags=["system"])
def health() -> dict[str, Any]:
    return health_payload()


@app.post(
    "/api/v1/telegram/webhook",
    tags=["research"],
    dependencies=[Depends(require_telegram_webhook)],
)
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Answer Leon's private Telegram queries with current Finviz data."""

    settings = get_settings()
    payload = await request.json()
    if not isinstance(payload, dict):
        return {"status": "ignored"}
    message = payload.get("message")
    if not isinstance(message, dict):
        return {"status": "ignored"}
    chat = message.get("chat")
    text = message.get("text")
    if (
        not isinstance(chat, dict)
        or str(chat.get("id", "")) != settings.telegram_chat_id.get_secret_value()
        or not isinstance(text, str)
    ):
        return {"status": "ignored"}

    normalised = text.strip()
    if normalised.lower() in {"/start", "/help"}:
        response = "\n".join(
            (
                "LMIO 查询帮助",
                "直接发送股票代码，例如：SNDK",
                "也可以发送：/quote SNDK",
                "命令：/status /health /top3 /top10 /news /options /help",
                "系统只提供研究信息，不会执行交易。",
            )
        )
    elif normalised.lower() == "/status":
        latest = get_service().store.latest_provider_health()
        if latest is None:
            response = "LMIO 尚无 Finviz 刷新记录。请稍后再试。"
        else:
            response = "\n".join(
                (
                    "LMIO · Finviz 连接状态",
                    f"状态：{latest['state']}",
                    f"最近检查：{latest['created_at']}",
                    "仅供研究与决策支持；不会执行交易。",
                )
            )
    elif normalised.lower() == "/health":
        counts = get_service().store.counts()
        latest_run = get_service().store.history_json("pipeline_runs", 1)
        pipeline = latest_run[0] if latest_run else None
        response = "\n".join(
            (
                "LMIO · 系统健康",
                f"数据库：{get_service().store.connectivity_check()['status']}",
                f"流水线：{pipeline['status'] if pipeline else '尚无运行'}",
                f"报告记录：{counts.get('reports', 0)}",
                "交易能力：关闭（实盘与模拟均关闭）",
                "仅供研究与决策支持；不会执行交易。",
            )
        )
    elif normalised.lower() in {"/top3", "/top10"}:
        report = get_service().store.latest_json("reports") or {}
        key = "top_3" if normalised.lower() == "/top3" else "top_10"
        candidates = list(report.get(key) or [])
        title = "今日 Top 3" if key == "top_3" else "今日 Top 10"
        if not candidates:
            status = dict(report.get("top_3_status") or {})
            response = f"LMIO · {title}\n当前不可用：{status.get('message', '尚无合格候选。')}"
        else:
            lines = [
                f"{index}. {item['symbol']} · {float(item['total_score']):.1f} · {item['strategy']}"
                for index, item in enumerate(candidates, start=1)
            ]
            response = "\n".join([f"LMIO · {title}", *lines, "数据若已过期会在候选详情中标明。"])
    elif normalised.lower() == "/news":
        events = get_service().latest_news(limit=5)
        if not events:
            response = "LMIO · 重要新闻\n尚无已验证的官方新闻记录。"
        else:
            response = "\n".join(
                [
                    "LMIO · 重要新闻",
                    *[
                        f"- {item['headline']} · {item['source']} · {item['published_at']}"
                        for item in events
                    ],
                    "新闻只触发研究，必须由价格确认。",
                ]
            )
    elif normalised.lower().startswith("/options"):
        requested = normalised.removeprefix("/options").strip().upper()
        symbol = requested if requested and requested.replace(".", "").isalnum() else None
        board = _options_board_payload(symbol)
        candidates = list(board.get("candidates") or [])[:5]
        provider = dict(board.get("provider") or {})
        high_volume = dict(board.get("high_volume") or {})
        active_tickers = list(high_volume.get("watchlist") or high_volume.get("tickers") or [])[:5]
        active_lines = [
            (f"- {dict(item).get('symbol')} · Cboe 榜单量 {dict(item).get('leaderboard_volume')}")
            for item in active_tickers
        ]
        if not candidates:
            response = "\n".join(
                (
                    "LMIO · Options Trading（非交易信号）",
                    f"资料状态：{provider.get('state', 'not_verified')}",
                    f"最近观察：{provider.get('last_observed_at') or '尚无'}",
                    "当前没有经过两次确认的异常期权候选。",
                    "Cboe 高成交量标的（至少延迟 20 分钟）：",
                    *(active_lines or ["- 当前时段没有可验证榜单；保留最后一批有数据的记录。"]),
                    "LMIO 不会因此执行任何订单。",
                )
            )
        else:
            lines = []
            for item in candidates:
                analysis = dict(item.get("analysis") or {})
                right = "Call" if item.get("right") == "call" else "Put"
                lines.append(
                    f"- {item.get('symbol')} {item.get('expiry')} "
                    f"{item.get('strike')} {right} · Vol/OI "
                    f"{analysis.get('volume_oi_ratio')}"
                )
            response = "\n".join(
                (
                    "LMIO · Options Trading（非交易信号）",
                    *lines,
                    "Cboe 高成交量标的（至少延迟 20 分钟）：",
                    *(active_lines or ["- 当前无可验证榜单。"]),
                    "必须核对新闻、标的走势及次日 OI；LMIO 不会下单。",
                )
            )
    else:
        symbol = parse_symbol_query(normalised)
        if symbol is None:
            response = "请输入有效股票代码，例如 SNDK，或发送 /help。"
        else:
            try:
                snapshot = get_service().finviz_symbol_snapshot(symbol)
            except RuntimeError:
                response = f"{symbol} 的 Finviz 查询暂时失败。旧数据未被修改，请稍后重试。"
            else:
                if snapshot is None:
                    response = f"Finviz 当前没有返回 {symbol} 的可验证数据。"
                elif not hasattr(get_service().store, "latest_json"):
                    response = format_symbol_research(snapshot)
                else:
                    report = get_service().store.latest_json("reports") or {}
                    ranked = list(report.get("top_10") or [])
                    candidate = next(
                        (
                            dict(item, rank=index)
                            for index, item in enumerate(ranked, 1)
                            if item.get("symbol") == symbol
                        ),
                        None,
                    )
                    valuations = get_service().store.history_json("valuation_runs", 200)
                    valuation = next(
                        (
                            item.get("result_payload")
                            for item in valuations
                            if item.get("symbol") == symbol
                        ),
                        None,
                    )
                    confirmations = get_service().store.history_json(
                        "news_price_confirmations", 200
                    )
                    latest_news = next(
                        (
                            item.get("payload")
                            for item in confirmations
                            if symbol in item.get("payload", {}).get("affected_symbols", [])
                        ),
                        None,
                    )
                    response = format_symbol_research(
                        snapshot,
                        candidate=candidate,
                        valuation=valuation,
                        latest_news=latest_news,
                    )

    delivery = queue_or_send(
        get_service().store,
        response,
        bot_token=settings.telegram_bot_token.get_secret_value(),
        chat_id=settings.telegram_chat_id.get_secret_value(),
        kind=MessageKind.IMMEDIATE_ALERT,
        max_per_hour=30,
        dedupe_context=f"telegram-update:{payload.get('update_id', 'unknown')}",
    )
    audit_event("telegram_query_processed", delivery=delivery)
    return {"status": "accepted", "delivery": delivery}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/ready", tags=["system"])
def ready() -> dict[str, Any]:
    settings = get_settings()
    service = get_service()
    payload = health_payload()
    payload["integrations"] = settings.integration_readiness()
    latest_provider = service.store.latest_provider_health()
    payload["provider_status"] = (
        latest_provider["state"]
        if latest_provider is not None
        else (
            "configured_not_verified"
            if any(settings.integration_readiness().values())
            else "not_configured"
        )
    )
    payload["latest_provider"] = latest_provider
    payload["store"] = {"status": "ready", "counts": service.store.counts()}
    payload["operational_health"] = build_system_health(service.store, settings)
    audit_event("readiness_checked", environment=payload["environment"])
    return payload


@app.get("/api/status", tags=["system"])
def api_status() -> dict[str, Any]:
    return ready()


@app.get("/api/v1/system-health", tags=["system"])
def system_health() -> dict[str, object]:
    return build_system_health(get_service().store, get_settings())


@app.post(
    "/api/v1/providers/ibkr/heartbeat",
    tags=["providers"],
)
def ibkr_bridge_heartbeat(
    heartbeat: IBKRBridgeHeartbeat,
    _principal: Annotated[Principal, Depends(require_ibkr_bridge)],
) -> dict[str, object]:
    """Record a minimal, outbound-only heartbeat from Leon's local paper TWS."""

    now = datetime.now(UTC)
    observed_at = heartbeat.observed_at.astimezone(UTC)
    if observed_at < now - timedelta(minutes=5) or observed_at > now + timedelta(minutes=1):
        raise HTTPException(
            status_code=422,
            detail="IBKR heartbeat timestamp is outside the allowed window.",
        )
    state = heartbeat.provider_state()
    record_id = get_service().store.append_json(
        "provider_health",
        {
            "provider": "ibkr_tws_paper",
            "state": state,
            "payload": heartbeat.safe_payload(),
        },
    )
    audit_event(
        "ibkr_bridge_heartbeat_recorded",
        state=state,
        paper_account_confirmed=heartbeat.paper_account_confirmed,
        news_provider_count=len(heartbeat.news_providers),
    )
    return {
        "status": "recorded",
        "provider": "ibkr_tws_paper",
        "state": state,
        "record_id": record_id,
        "recorded_at": now.isoformat(),
    }


def _previous_option_candidate(
    history: list[dict[str, Any]],
    *,
    contract_key: str,
    observed_at: datetime,
) -> bool:
    """Require a second bounded observation before alerting Leon."""

    for item in history:
        payload = dict(item.get("payload") or {})
        analysis = dict(payload.get("analysis") or {})
        if analysis.get("contract_key") != contract_key or not analysis.get("candidate"):
            continue
        try:
            previous_at = datetime.fromisoformat(str(payload["observed_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        gap = observed_at - previous_at.astimezone(UTC)
        if timedelta(minutes=2) <= gap <= timedelta(minutes=30):
            return True
    return False


def _record_options_batch(batch: OptionBatch) -> dict[str, object]:
    """Persist one bounded, source-attributed option research batch."""
    now = datetime.now(UTC)
    observed_at = batch.observed_at.astimezone(UTC)
    if observed_at < now - timedelta(minutes=20) or observed_at > now + timedelta(minutes=1):
        raise HTTPException(
            status_code=422,
            detail="Options batch timestamp is outside the window.",
        )

    service = get_service()
    existing = service.store.history_json("options_flow", 200)
    received = len(batch.observations)
    qualified = 0
    confirmed = 0
    stored = 0
    deliveries: list[str] = []
    symbols = sorted({item.symbol for item in batch.observations})
    field_coverage = {
        field: sum(
            1 for observation in batch.observations if getattr(observation, field) is not None
        )
        for field in ("bid", "ask", "last", "volume", "open_interest")
    }

    for observation in batch.observations:
        payload = persisted_option(observation)
        analysis = dict(payload["analysis"])
        if not analysis["candidate"]:
            continue
        qualified += 1
        is_confirmed = _previous_option_candidate(
            existing,
            contract_key=str(analysis["contract_key"]),
            observed_at=observation.observed_at,
        )
        payload["confirmation_state"] = "confirmed_twice" if is_confirmed else "first_seen"
        payload["confirmation_count"] = 2 if is_confirmed else 1
        if not service.store.mark_ingestion_fingerprint(observation.fingerprint, "options_flow"):
            continue
        service.store.append_json(
            "options_flow",
            {
                "symbol": observation.symbol,
                "source": observation.source,
                "source_url": observation.source_url,
                "observed_at": observation.observed_at.isoformat(),
                "schema_version": "options-v1",
                "payload": payload,
            },
        )
        stored += 1
        if not is_confirmed:
            continue
        confirmed += 1
        delivery = queue_or_send(
            service.store,
            format_option_alert(payload),
            bot_token=service.settings.telegram_bot_token.get_secret_value(),
            chat_id=service.settings.telegram_chat_id.get_secret_value(),
            kind=MessageKind.AFTER_OPEN,
            max_per_hour=10,
            dedupe_context=f"options:{observation.contract_key}:{observation.observed_at.date()}",
        )
        deliveries.append(delivery)

    provider_state = "ready" if received else "degraded"
    service.store.append_json(
        "provider_health",
        {
            "provider": (
                "ibkr_options_delayed"
                if batch.source == "ibkr_tws_paper_delayed"
                else "barchart_manual_csv"
            ),
            "state": provider_state,
            "payload": {
                "observed_at": observed_at.isoformat(),
                "source": batch.source,
                "data_mode": ("delayed" if batch.source == "ibkr_tws_paper_delayed" else "manual"),
                "received": received,
                "qualified": qualified,
                "confirmed": confirmed,
                "stored": stored,
                "symbols": symbols,
                "field_coverage": field_coverage,
                "execution_allowed": False,
                "data_scope": "bounded_contract_market_data_only",
            },
        },
    )
    audit_event(
        "ibkr_options_batch_recorded",
        received=received,
        qualified=qualified,
        confirmed=confirmed,
        stored=stored,
        symbols=symbols,
    )
    return {
        "status": "recorded",
        "received": received,
        "qualified": qualified,
        "confirmed": confirmed,
        "stored": stored,
        "telegram": deliveries,
        "execution_allowed": False,
        "recorded_at": now.isoformat(),
    }


@app.post("/api/v1/providers/ibkr/options", tags=["providers"])
def ibkr_options_batch(
    batch: OptionBatch,
    _principal: Annotated[Principal, Depends(require_ibkr_bridge)],
) -> dict[str, object]:
    """Persist bounded delayed option research from Leon's local paper TWS."""

    if batch.source != "ibkr_tws_paper_delayed":
        raise HTTPException(status_code=422, detail="IBKR endpoint requires IBKR source.")
    return _record_options_batch(batch)


class BarchartCSVImport(BaseModel):
    csv_text: str = Field(min_length=1, max_length=1_000_000)


@app.post(
    "/api/v1/providers/options/barchart-csv",
    tags=["providers"],
    dependencies=[Depends(require_admin)],
)
def import_barchart_csv(payload: BarchartCSVImport) -> dict[str, object]:
    """Import a CSV downloaded by Leon; never log in to or scrape Barchart."""

    try:
        batch = parse_barchart_csv(payload.csv_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _record_options_batch(batch)


def _latest_acceptance_feedback() -> list[dict[str, Any]]:
    return [
        item
        for item in get_service().store.history_json("user_feedback", 200)
        if str(item.get("subject_type")) == "operator_acceptance"
    ]


@app.get("/api/v1/acceptance", tags=["system"])
def operator_acceptance() -> dict[str, object]:
    """Return safe release evidence for the protected operator workspace."""

    service = get_service()
    settings = get_settings()
    health = build_system_health(service.store, settings)
    connection = service.store.connectivity_check()
    schema = service.store.schema_check()
    runs = service.store.history_json("pipeline_runs", 10)
    latest_run = runs[0] if runs else None
    latest_run_id = str(latest_run.get("run_id")) if latest_run else None
    stages = [
        item
        for item in service.store.history_json("pipeline_stages", 200)
        if latest_run_id and str(item.get("run_id")) == latest_run_id
    ]
    provider_events = service.store.history_json("provider_health", 200)
    live_success = next(
        (item for item in provider_events if str(item.get("state")) == "ready"),
        None,
    )
    feedback = _latest_acceptance_feedback()
    controls = [
        item
        for item in service.store.history_json("system_events", 200)
        if str(item.get("event_type")) == "acceptance_control"
    ]
    latest_decision = feedback[0] if feedback else None
    configured = settings.integration_readiness()
    unattended = scheduler_status(service.store)
    return {
        "release": {
            "label": settings.release_label,
            "version": __version__,
            "sha": settings.resolved_release_sha,
            "environment": settings.environment,
            "schema_versions": schema.get("schema_versions", []),
            "required_schema": 12,
        },
        "readiness": {
            "status": health["status"],
            "database": connection,
            "latest_pipeline": latest_run,
            "blockers": health.get("stale_or_unknown", []),
            "trading": health["safety"],
        },
        "evidence_levels": [
            {"level": "code", "label": "代码已实现", "state": "verified_in_repository"},
            {
                "level": "automated",
                "label": "自动检查",
                "state": (
                    "verified_for_recorded_sha"
                    if settings.resolved_release_sha != "unrecorded"
                    else "awaiting_release_sha"
                ),
            },
            {
                "level": "configured",
                "label": "环境已配置",
                "state": "partially_configured" if any(configured.values()) else "not_configured",
            },
            {
                "level": "live",
                "label": "真实提供商验证",
                "state": "verified" if live_success else "awaiting_live_evidence",
                "checked_at": live_success.get("created_at") if live_success else None,
            },
            {
                "level": "unattended",
                "label": "无人值守运行",
                "state": unattended["executor_process"],
            },
            {
                "level": "operator",
                "label": "Leon 验收",
                "state": (
                    latest_decision.get("decision")
                    if latest_decision
                    else "awaiting_operator_acceptance"
                ),
                "checked_at": latest_decision.get("created_at") if latest_decision else None,
            },
        ],
        "pipeline": {
            "required_stage_count": 21,
            "latest_run_id": latest_run_id,
            "stages": sorted(stages, key=lambda item: int(item.get("stage_order", 0))),
        },
        "feedback": feedback[:50],
        "control_history": controls[:20],
        "scheduler": unattended,
        "providers": health["providers"],
        "freshness": health["freshness"],
        "synthetic_or_fixture": bool(
            latest_run
            and str(dict(latest_run.get("payload") or {}).get("data_mode", ""))
            not in {"authorised_finviz_api", "operational"}
        ),
    }


class AcceptanceControlInput(BaseModel):
    action: str = Field(
        pattern="^(smoke_test|provider_refresh|manual_pipeline|telegram_drain|health_refresh|scheduler_inspect|backup_status)$"
    )


class OptionsScreenshotInput(BaseModel):
    image_data_url: str = Field(min_length=32, max_length=2_700_000)


@app.post("/api/v1/options/screenshot-analysis", tags=["research"])
def analyse_options_screenshot(
    payload: OptionsScreenshotInput,
    principal: Annotated[Principal, Depends(require_dashboard_refresh)],
) -> dict[str, object]:
    """Analyse a transient owner-supplied screenshot without retaining the image."""

    try:
        mime_type, image_bytes = validate_options_screenshot_data_url(payload.image_data_url)
        result = get_service().analyse_options_screenshot(
            payload.image_data_url,
            mime_type=mime_type,
            image_bytes=image_bytes,
            actor_role=str(principal.role),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        status = 429 if "cap reached" in str(error).lower() else 503
        raise HTTPException(status_code=status, detail=str(error)) from error
    audit_event(
        "options_screenshot_analysed",
        actor=principal.actor_id,
        role=str(principal.role),
        resource_type="options_research",
        resource_id=str(result.get("analysed_at", "latest")),
        payload={
            "image_bytes": image_bytes,
            "image_retained": False,
            "order_created": False,
        },
    )
    return result


@app.post("/api/v1/operator/full-refresh", tags=["system"])
def operator_full_refresh(
    principal: Annotated[Principal, Depends(require_dashboard_refresh)],
) -> dict[str, object]:
    """Refresh every connected research source without one long pipeline request.

    This endpoint is intentionally narrow: it has no arbitrary action input and
    no trading, payment, configuration, or account-management capability.
    """

    service = get_service()
    started_at = datetime.now(UTC)
    run_id = f"operator-refresh-{started_at:%Y%m%dT%H%M%S}"
    component_statuses: dict[str, str] = {}
    unavailable: list[str] = []

    refreshes = (
        ("finviz_market_strategy_and_report", service.refresh_finviz),
        ("cboe_high_volume_options", service.refresh_cboe_options),
        ("official_macro_sec_and_ai_news", service.refresh_official_news),
        ("due_outcomes", service.process_due_outcomes),
        ("strategy_performance", service.aggregate_strategy_performance),
    )
    for component, refresh in refreshes:
        try:
            result = refresh()
        except Exception as error:
            component_statuses[component] = "unavailable"
            unavailable.append(component)
            service.store.append_json(
                "system_events",
                {
                    "event_type": "operator_refresh_component_unavailable",
                    "severity": "warning",
                    "payload": {
                        "run_id": run_id,
                        "component": component,
                        "error_class": type(error).__name__,
                        "trading_action": False,
                        "payment_action": False,
                    },
                },
            )
            continue

        raw_status = str(result.get("status", "completed"))
        nested_statuses = {
            str(value.get("status"))
            for value in result.values()
            if isinstance(value, dict) and value.get("status") is not None
        }
        if raw_status in {"failed", "unavailable"} or nested_statuses.intersection(
            {"failed", "unavailable"}
        ):
            component_statuses[component] = "unavailable"
            unavailable.append(component)
        elif raw_status in {"partial", "degraded"} or nested_statuses.intersection(
            {"partial", "degraded", "disabled"}
        ):
            component_statuses[component] = "partial"
        else:
            component_statuses[component] = "completed"

    try:
        build_system_health(service.store, service.settings)
    except Exception as error:
        component_statuses["system_health"] = "unavailable"
        unavailable.append("system_health")
        service.store.append_json(
            "system_events",
            {
                "event_type": "operator_refresh_component_unavailable",
                "severity": "warning",
                "payload": {
                    "run_id": run_id,
                    "component": "system_health",
                    "error_class": type(error).__name__,
                    "trading_action": False,
                    "payment_action": False,
                },
            },
        )
    else:
        component_statuses["system_health"] = "completed"

    finished_at = datetime.now(UTC)
    partial = [name for name, status in component_statuses.items() if status == "partial"]
    status = "partial" if unavailable or partial else "succeeded"
    service.store.append_json(
        "system_events",
        {
            "event_type": "operator_full_refresh",
            "severity": status,
            "payload": {
                "actor": principal.actor_id,
                "role": principal.role,
                "run_id": run_id,
                "completed_at": finished_at.isoformat(),
                "component_statuses": component_statuses,
                "unavailable_components": unavailable,
                "partial_components": partial,
                "trading_action": False,
                "payment_action": False,
            },
        },
    )
    return {
        "status": status,
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "component_statuses": component_statuses,
        "unavailable_components": unavailable,
        "partial_components": partial,
        "trading_action": False,
        "payment_action": False,
    }


@app.post("/api/v1/acceptance/control", tags=["system"])
def acceptance_control(
    payload: AcceptanceControlInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, object]:
    """Run bounded, non-trading operator checks from the protected dashboard."""

    service = get_service()
    if payload.action == "smoke_test":
        result: dict[str, object] = {"health": health_payload(), "ready": ready()}
    elif payload.action == "provider_refresh":
        result = _refresh_finviz()
    elif payload.action == "manual_pipeline":
        result = service.run_operational_pipeline()
    elif payload.action == "telegram_drain":
        result = drain_outbox(
            service.store,
            bot_token=service.settings.telegram_bot_token.get_secret_value(),
            chat_id=service.settings.telegram_chat_id.get_secret_value(),
        )
    elif payload.action == "health_refresh":
        result = build_system_health(service.store, service.settings)
    elif payload.action == "scheduler_inspect":
        result = scheduler_status(service.store)
    else:
        result = {
            "backend": service.settings.store_backend,
            "schema": service.store.schema_check(),
            "recovery_capability": "verified_primitive",
            "fresh_backup_required_before_protected_migration": True,
        }
    service.store.append_json(
        "system_events",
        {
            "event_type": "acceptance_control",
            "severity": "completed",
            "payload": {
                "action": payload.action,
                "actor": principal.actor_id,
                "completed_at": datetime.now(UTC).isoformat(),
                "trading_action": False,
            },
        },
    )
    audit_event("acceptance_control_run", action=payload.action, actor=principal.actor_id)
    return {
        "action": payload.action,
        "actor": principal.actor_id,
        "completed_at": datetime.now(UTC).isoformat(),
        "result": result,
        "trading_action": False,
    }


@app.get("/api/v1/providers/health", tags=["system"])
def providers_health() -> dict[str, Any]:
    readiness = get_settings().integration_readiness()
    providers = {
        name.removesuffix("_configured"): {
            "state": "configured_not_verified" if configured else "disabled",
        }
        for name, configured in readiness.items()
    }
    # Provider cards must use the latest result for that provider, not the
    # latest result across every provider. A news refresh commonly writes SEC
    # or macro health after Finviz and must not overwrite the Finviz card.
    for item in get_service().store.history_json("provider_health", 1000):
        provider = str(item.get("provider", "")).strip()
        if not provider or (provider in providers and "checked_at" in providers[provider]):
            continue
        providers[provider] = {
            "provider": provider,
            "state": item.get("state", "unavailable"),
            "detail": dict(item.get("payload") or {}).get("detail"),
            "checked_at": item.get("created_at"),
        }
    return providers


app.get("/api/providers/health", tags=["system"])(providers_health)


@app.get("/api/v1/command-centre", tags=["research"])
def command_centre_data() -> dict[str, Any]:
    """Return one truthful, non-sensitive operating view for the LMIO dashboard."""

    service = get_service()
    settings = get_settings()
    report = service.store.latest_json("reports")
    if report is None:
        raise HTTPException(status_code=404, detail="No report exists.")

    regime = dict(report.get("regime") or {})
    research_queue = list(report.get("top_10") or [])[:3]
    qualified_priorities = list(report.get("top_3") or [])
    urgent_events = [
        event
        for event in service.latest_news(limit=50)
        if event.get("significance", 0) >= 80 and event.get("confidence", 0) >= 0.7
    ][:5]
    risk_blocks = [
        *list(regime.get("blocked_sectors") or []),
        *list(regime.get("blocked_symbols") or []),
    ]
    warnings = list(report.get("warnings") or [])
    if regime.get("label") == "Unverified":
        warnings.append("市场环境尚未由独立基准数据核实；不得把候选排序视为交易指令。")
    if not qualified_priorities and research_queue:
        warnings.append("当前 Top 3 仅为研究队列；估值和确认条件不足，尚无优先机会。")

    latest_provider = service.store.latest_provider_health()
    counts = service.store.counts()
    integrations = settings.integration_readiness()
    return {
        "generated_at": report.get("generated_at"),
        "data_mode": report.get("data_mode"),
        "regime": regime,
        "funnel": report.get("funnel") or {},
        "research_queue": research_queue,
        "qualified_priorities": qualified_priorities,
        "important_events": urgent_events,
        "risk_blocks": risk_blocks,
        "warnings": list(dict.fromkeys(warnings)),
        "provider_health": providers_health(),
        "latest_provider": latest_provider,
        "telegram": {
            "configured": bool(integrations.get("telegram_configured")),
            "private_queries_configured": bool(integrations.get("telegram_queries_configured")),
            "delivery_records": counts.get("telegram_deliveries", 0),
        },
        "storage": {"status": "ready", "counts": counts},
        "safety": {
            "can_trade": settings.can_trade,
            "live_trading_enabled": settings.live_trading_enabled,
            "paper_trading_enabled": settings.paper_trading_enabled,
        },
    }


def _refresh_finviz(message_kind: MessageKind = MessageKind.PREMARKET) -> dict[str, object]:
    try:
        result = get_service().refresh_finviz(message_kind=message_kind)
    except RuntimeError as error:
        audit_event("finviz_refresh_failed", error=type(error.__cause__).__name__)
        raise HTTPException(
            status_code=502,
            detail="Finviz refresh failed safely; existing LMIO data was preserved.",
        ) from error
    audit_event(
        "finviz_refresh_completed",
        equities_received=result["equities_received"],
        candidates_found=result["candidates_found"],
        telegram=result["telegram"],
    )
    return result


@app.get(
    "/api/v1/providers/finviz/refresh",
    tags=["research"],
    dependencies=[Depends(require_cron)],
)
def scheduled_finviz_refresh() -> dict[str, object]:
    """Run the protected server-side refresh invoked by Vercel Cron."""

    return _refresh_finviz()


@app.post(
    "/api/v1/providers/finviz/refresh",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def manual_finviz_refresh() -> dict[str, object]:
    """Allow an authorised operator to refresh without waiting for the schedule."""

    return _refresh_finviz()


def _refresh_official_news() -> dict[str, object]:
    result = get_service().refresh_official_news()
    audit_event("official_news_refresh_completed", result=result)
    return result


@app.get(
    "/api/v1/providers/news/refresh",
    tags=["research"],
    dependencies=[Depends(require_cron)],
)
def scheduled_official_news_refresh() -> dict[str, object]:
    """Refresh allowlisted government releases and SEC events server-side."""

    return _refresh_official_news()


@app.post(
    "/api/v1/providers/news/refresh",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def manual_official_news_refresh() -> dict[str, object]:
    return _refresh_official_news()


@app.get(
    "/api/v1/scheduler/{job_id}",
    tags=["system"],
    dependencies=[Depends(require_cron)],
)
def execute_scheduled_job(job_id: str) -> dict[str, object]:
    """Execute one manifest-declared job with its same-window lock."""

    try:
        return run_scheduled_job(get_service(), job_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/v1/demo/run", tags=["research"], dependencies=[Depends(require_admin)])
def run_demo() -> dict[str, object]:
    if not get_settings().enable_demo_mode:
        raise HTTPException(status_code=404, detail="Synthetic replay is disabled.")
    audit_event("synthetic_daily_run_started")
    return get_service().run_demo_daily()


@app.get("/api/v1/reports/latest", tags=["research"])
def latest_report() -> dict[str, Any]:
    report = get_service().store.latest_json("reports")
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No operational report exists.",
        )
    return report


@app.get("/api/market/regime", tags=["research"])
def market_regime() -> dict[str, Any]:
    return dict(latest_report()["regime"])


@app.get("/api/market/premarket-brief", tags=["research"])
def premarket_brief() -> dict[str, Any]:
    report = latest_report()
    return {
        "generated_at": report["generated_at"],
        "data_mode": report["data_mode"],
        "message_zh": report["message_zh"],
        "warnings": report["warnings"],
    }


@app.get("/api/v1/screens/latest", tags=["research"])
def latest_screen() -> list[dict[str, Any]]:
    screen = get_service().store.latest_json("screen_runs")
    if screen is None:
        raise HTTPException(status_code=404, detail="No screen run exists.")
    if not isinstance(screen, list):
        raise HTTPException(status_code=500, detail="Stored screen run is malformed.")
    return screen


app.get("/api/screens", tags=["research"])(latest_screen)


@app.post(
    "/api/screens/run",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def run_screens() -> dict[str, object]:
    return run_demo()


@app.get("/api/screens/{run_id}/results", tags=["research"])
def screen_results(run_id: int) -> dict[str, Any]:
    for record in get_service().store.history_json("screen_runs", 200):
        if record["id"] == run_id:
            return dict(record)
    raise HTTPException(status_code=404, detail="Screen run not found.")


@app.get("/api/v1/reports/history", tags=["research"])
def report_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("reports", limit)


@app.get("/api/v1/valuations/history", tags=["valuation"])
def valuation_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("valuation_runs", limit)


@app.get("/api/v1/candidates", tags=["research"])
def candidate_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("candidate_transitions", limit)


app.get("/api/candidates", tags=["research"])(candidate_history)


@app.get("/api/candidates/{symbol}", tags=["research"])
def candidate_by_symbol(symbol: str) -> list[dict[str, Any]]:
    normalised = symbol.upper()
    screen = get_service().store.latest_json("screen_runs") or []
    result = [item for item in screen if item["symbol"].upper() == normalised]
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return result


@app.get("/api/v1/research", tags=["research"])
def research_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("research_packs", limit)


@app.get("/api/v1/news", tags=["research"])
def news_history(limit: int = 100) -> list[dict[str, Any]]:
    return get_service().latest_news(limit)


@app.get("/api/v1/news/research-board", tags=["research"])
def news_research_board(limit: int = 100) -> dict[str, Any]:
    """Return complete official-source coverage with evidence-bound research lenses."""

    return build_news_research_board(get_service().latest_news(limit))


@app.get("/api/v1/ownership", tags=["research"])
def ownership_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("ownership_events", limit)


@app.get("/api/v1/plans", tags=["research"])
def plan_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("conditional_plans", limit)


@app.get("/api/v1/signals", tags=["research"])
def signal_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("signals", limit)


@app.post("/api/v1/plans/{plan_id}/signal", tags=["research"])
def create_research_signal(
    plan_id: int,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, object]:
    try:
        return get_service().create_signal_from_approved_plan(
            plan_id,
            actor=principal.actor_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/v1/audit/lineage/{run_id}", tags=["system"])
def operational_lineage(run_id: str) -> dict[str, Any]:
    """Return safe evidence references for one run; never licensed source rows."""

    lineage = next(
        (
            item
            for item in get_service().store.history_json("operational_lineage", 200)
            if str(item.get("run_id")) == run_id
        ),
        None,
    )
    if lineage is None:
        raise HTTPException(status_code=404, detail="Operational lineage not found.")
    signals = [
        {
            "id": item["id"],
            "signal_id": dict(item.get("payload") or {}).get("signal_id"),
            "candidate_id": dict(item.get("payload") or {}).get("candidate_id"),
        }
        for item in get_service().store.history_json("signals", 200)
        if str(dict(item.get("payload") or {}).get("run_id")) == run_id
    ]
    outcomes = [
        {
            "id": item["id"],
            "signal_id": dict(item.get("payload") or {}).get("signal_id"),
            "horizon": item.get("horizon"),
            "status": dict(item.get("payload") or {}).get("status"),
        }
        for item in get_service().store.history_json("signal_outcomes", 200)
        if str(dict(item.get("payload") or {}).get("run_id")) == run_id
    ]
    return {
        "run_id": run_id,
        "lineage": lineage["payload"],
        "signals": signals,
        "outcomes": outcomes,
        "raw_provider_rows_exposed": False,
    }


@app.get("/api/v1/performance", tags=["research"])
def performance_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("strategy_performance", limit)


@app.get("/api/v1/watchlists", tags=["research"])
def watchlist_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("watchlists", limit)


class WatchlistInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


class WatchlistMemberInput(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9.-]{0,9}$")
    action: str = Field(pattern="^(add|remove)$")
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


@app.post("/api/v1/watchlists", tags=["research"])
def create_watchlist(
    payload: WatchlistInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    prior = [
        item
        for item in get_service().store.history_json("watchlists", 200)
        if str(item.get("name", "")).casefold() == payload.name.casefold()
    ]
    version = len(prior) + 1
    record = {
        **payload.model_dump(mode="json"),
        "actor": principal.actor_id,
        "role": principal.role,
        "version": version,
        "action": "created",
    }
    record_id = get_service().store.append_json(
        "watchlists", {"name": payload.name, "payload": record}
    )
    return {"id": record_id, "version": version, "status": "created"}


@app.post("/api/v1/watchlists/{watchlist_id}/members", tags=["research"])
def change_watchlist_member(
    watchlist_id: int,
    payload: WatchlistMemberInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    parent = next(
        (
            item
            for item in get_service().store.history_json("watchlists", 200)
            if int(item["id"]) == watchlist_id
        ),
        None,
    )
    if parent is None:
        raise HTTPException(status_code=404, detail="Watchlist not found.")
    prior = [
        item
        for item in get_service().store.history_json("watchlist_members", 200)
        if int(item.get("watchlist_id", -1)) == watchlist_id
        and str(item.get("symbol", "")).upper() == payload.symbol.upper()
    ]
    version = len(prior) + 1
    record = {
        **payload.model_dump(mode="json"),
        "symbol": payload.symbol.upper(),
        "actor": principal.actor_id,
        "role": principal.role,
        "version": version,
        "watchlist_name": parent["name"],
    }
    record_id = get_service().store.append_json(
        "watchlist_members",
        {
            "watchlist_id": watchlist_id,
            "symbol": payload.symbol.upper(),
            "payload": record,
        },
    )
    return {"id": record_id, "version": version, "status": payload.action}


class FeedbackInput(BaseModel):
    subject_type: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1, max_length=120)
    decision: str = Field(pattern="^(approved|rejected|needs_revision)$")
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)
    verified_identity: str | None = Field(default=None, max_length=200)
    verified_email: str | None = Field(default=None, max_length=320)
    verified_role: str | None = Field(default=None, pattern="^(owner|operator|reviewer)$")


@app.post(
    "/api/v1/feedback",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def record_feedback(
    payload: FeedbackInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    record = payload.model_dump(mode="json")
    record_id = get_service().store.append_json(
        "user_feedback",
        {
            "subject_type": payload.subject_type,
            "subject_id": payload.subject_id,
            "decision": payload.decision,
            "actor": principal.actor_id,
            "payload": {**record, "actor": principal.actor_id, "role": principal.role},
        },
    )
    audit_event(
        "user_feedback_recorded",
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        decision=payload.decision,
        actor=principal.actor_id,
    )
    return {"id": record_id, "status": "recorded"}


@app.post(
    "/api/v1/valuation/meta-acceptance",
    tags=["valuation"],
    dependencies=[Depends(require_admin)],
)
def meta_acceptance() -> dict[str, object]:
    audit_event("meta_acceptance_run_started")
    return get_service().run_meta_acceptance()


@app.post(
    "/api/v1/candidates/research",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def research_candidates() -> list[dict[str, object]]:
    try:
        return get_service().research_latest()
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/api/candidates/{symbol}/research",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def research_candidate(symbol: str) -> dict[str, object]:
    try:
        records = get_service().research_latest(limit=20)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    for record in records:
        if str(record["symbol"]).upper() == symbol.upper():
            return record
    raise HTTPException(status_code=404, detail="Candidate not found in latest screen.")


@app.post(
    "/api/candidates/{symbol}/feedback",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def candidate_feedback(
    symbol: str,
    payload: FeedbackInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    if payload.subject_id.upper() != symbol.upper():
        raise HTTPException(status_code=422, detail="Feedback subject does not match symbol.")
    return record_feedback(payload, principal)


@app.post(
    "/api/valuation/{symbol}/run",
    tags=["valuation"],
    dependencies=[Depends(require_admin)],
)
def run_symbol_valuation(symbol: str) -> dict[str, object]:
    if symbol.upper() != "META":
        raise HTTPException(
            status_code=409,
            detail="No approved point-in-time valuation input exists for this symbol.",
        )
    return get_service().run_meta_acceptance()


@app.get("/api/valuation/{symbol}/history", tags=["valuation"])
def symbol_valuation_history(symbol: str) -> list[dict[str, Any]]:
    normalised = symbol.upper()
    return [
        record
        for record in get_service().store.history_json("valuation_runs", 200)
        if record["symbol"].upper() == normalised
    ]


@app.get("/api/valuation/{symbol}/latest", tags=["valuation"])
def latest_symbol_valuation(symbol: str) -> dict[str, Any]:
    history = symbol_valuation_history(symbol)
    if not history:
        raise HTTPException(status_code=404, detail="Valuation not found.")
    return history[0]


app.get("/api/news/events", tags=["research"])(news_history)


@app.post(
    "/api/news/check",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def check_news() -> dict[str, Any]:
    return {
        "status": "read_only_check",
        "stored_events": get_service().store.counts()["news_events"],
        "external_provider_call": False,
    }


class NewsAnalysisInput(BaseModel):
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


@app.post(
    "/api/news/{event_id}/analyse",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def analyse_news_event(event_id: str, payload: NewsAnalysisInput) -> dict[str, Any]:
    stored = get_service().store.news_event(event_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="News event not found.")
    event = NewsEvent.model_validate(stored)
    impact = news_impact_score(event)
    confirmation_record = next(
        (
            item
            for item in get_service().store.history_json("news_price_confirmations", 200)
            if item.get("payload", {}).get("source_url") == event.source_url
        ),
        None,
    )
    confirmation = (
        NewsPriceConfirmation.model_validate(confirmation_record["payload"])
        if confirmation_record is not None
        else None
    )
    reaction_confirmed = bool(
        confirmation is not None
        and confirmation.confirmation_state is ConfirmationState.CONFIRMED
        and not confirmation.missing_evidence
    )
    snapshot_references = (
        [f"news_price_confirmations:{confirmation_record['id']}"]
        if reaction_confirmed and confirmation_record is not None
        else []
    )
    plan = propose_news_plan(
        event,
        price_confirmation=reaction_confirmed,
        evidence_urls=payload.evidence_urls,
        market_snapshot_references=snapshot_references,
        run_id=f"news-analysis:{event_id}:{datetime.now(UTC).isoformat()}",
    )
    plan_payload = plan.model_dump(mode="json") if plan is not None else None
    plan_id = None
    if plan_payload is not None:
        plan_id = get_service().store.append_json(
            "conditional_plans",
            {
                "symbol": plan.symbol,
                "state": plan.state,
                "version": plan.version,
                "payload": plan_payload,
            },
        )
    audit_event(
        "news_event_analysed",
        event_id=event_id,
        impact_score=impact,
        conditional_plan_created=plan_id is not None,
    )
    return {
        "event_id": event_id,
        "impact_score": impact,
        "priority": "P0" if impact >= 85 else "P1" if impact >= 70 else "watch",
        "reaction_confirmed": reaction_confirmed,
        "conditional_plan_id": plan_id,
        "conditional_plan": plan_payload,
        "order_created": False,
    }


@app.get("/api/institutions/{symbol}", tags=["research"])
def institution_records(symbol: str) -> list[dict[str, Any]]:
    return [
        item
        for item in ownership_history(200)
        if item["symbol"].upper() == symbol.upper()
        and item["event_type"] == "institutional_holdings"
    ]


@app.get("/api/insiders/{symbol}", tags=["research"])
def insider_records(symbol: str) -> list[dict[str, Any]]:
    return [
        item
        for item in ownership_history(200)
        if item["symbol"].upper() == symbol.upper() and item["event_type"] == "insider_transaction"
    ]


app.get("/api/trade-plans", tags=["research"])(plan_history)
app.get("/api/reports", tags=["research"])(report_history)
app.get("/api/strategy-performance", tags=["research"])(performance_history)


def _options_board_payload(symbol: str | None = None) -> dict[str, object]:
    service = get_service()
    records = service.store.history_json("options_flow", 200)
    latest_screenshot_analysis = next(
        (
            {
                "analysed_at": item.get("observed_at") or item.get("created_at"),
                **dict(item.get("payload") or {}),
            }
            for item in records
            if item.get("source") == "openai_options_screenshot"
            and dict(item.get("payload") or {}).get("record_type") == "options_screenshot_analysis"
        ),
        None,
    )
    latest_by_contract: dict[str, dict[str, Any]] = {}
    for record in records:
        payload = dict(record.get("payload") or {})
        analysis = dict(payload.get("analysis") or {})
        contract_key = str(analysis.get("contract_key") or "")
        if not contract_key or (symbol and str(payload.get("symbol")) != symbol.upper()):
            continue
        latest_by_contract.setdefault(contract_key, payload)

    candidates = sorted(
        latest_by_contract.values(),
        key=lambda item: (
            int(item.get("confirmation_count") or 0),
            float(dict(item.get("analysis") or {}).get("volume_oi_ratio") or 0),
        ),
        reverse=True,
    )[:50]
    provider_events = [
        item
        for item in service.store.history_json("provider_health", 200)
        if item.get("provider") in {"ibkr_options_delayed", "barchart_manual_csv"}
    ]
    latest_provider = provider_events[0] if provider_events else None
    latest_payload = dict((latest_provider or {}).get("payload") or {})
    latest_time = latest_payload.get("observed_at")
    stale = True
    if latest_time:
        try:
            parsed = datetime.fromisoformat(str(latest_time).replace("Z", "+00:00"))
            stale = datetime.now(UTC) - parsed.astimezone(UTC) > timedelta(minutes=20)
        except ValueError:
            stale = True

    cboe_events = [
        item
        for item in service.store.history_json("provider_health", 200)
        if item.get("provider") == "cboe_options_most_active"
    ]
    latest_cboe_check = cboe_events[0] if cboe_events else None
    latest_cboe_snapshot = next(
        (
            item
            for item in cboe_events
            if item.get("state") == "ready"
            and int(dict(item.get("payload") or {}).get("total_contracts") or 0) > 0
        ),
        None,
    )
    cboe_payload = dict((latest_cboe_snapshot or {}).get("payload") or {})
    high_volume_tickers = list(cboe_payload.get("high_volume_tickers") or [])
    significant_watchlist = list(cboe_payload.get("significant_watchlist") or [])
    if symbol:
        high_volume_tickers = [
            item for item in high_volume_tickers if str(dict(item).get("symbol")) == symbol.upper()
        ]
        significant_watchlist = [
            item
            for item in significant_watchlist
            if str(dict(item).get("symbol")) == symbol.upper()
        ]
    cboe_contracts = [
        *list(cboe_payload.get("calls") or []),
        *list(cboe_payload.get("puts") or []),
    ]
    if symbol:
        cboe_contracts = [
            item for item in cboe_contracts if str(dict(item).get("symbol")) == symbol.upper()
        ]
    return {
        "title": "Options Trading / 期权研究",
        "purpose": "异常期权成交研究与提醒；不是买卖信号，不具备订单执行能力。",
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": {
            "name": (
                "Barchart manual CSV"
                if (latest_provider or {}).get("provider") == "barchart_manual_csv"
                else "IBKR TWS Paper delayed options"
            ),
            "state": (latest_provider or {}).get("state", "not_verified"),
            "stale": stale,
            "last_observed_at": latest_time,
            "data_mode": latest_payload.get("data_mode", "delayed"),
            "symbols": latest_payload.get("symbols", []),
            "records_received_last_batch": latest_payload.get("received", 0),
            "qualified_last_batch": latest_payload.get("qualified", 0),
            "field_coverage": latest_payload.get("field_coverage", {}),
        },
        "thresholds": {
            "minimum_volume": 500,
            "minimum_open_interest": 100,
            "minimum_volume_oi_ratio": 1.25,
            "minimum_option_price_usd": 0.10,
            "maximum_bid_ask_spread_pct": 20,
            "days_to_expiry": "7–60",
            "telegram_confirmation": "必须连续两次扫描达到门槛",
        },
        "candidates": candidates,
        "candidate_count": len(candidates),
        "screenshot_analysis": latest_screenshot_analysis,
        "high_volume": {
            "provider": "Cboe Options Exchange",
            "state": (latest_cboe_check or {}).get("state", "not_verified"),
            "last_checked_at": (latest_cboe_check or {}).get("created_at"),
            "market_timestamp": cboe_payload.get("market_timestamp"),
            "data_mode": cboe_payload.get("data_mode", "delayed_at_least_20_minutes"),
            "exchange_scope": cboe_payload.get(
                "exchange_scope",
                "Cboe Options Exchange only; not consolidated US options volume",
            ),
            "source_url": cboe_payload.get("source_url"),
            "tickers": high_volume_tickers[:25],
            "watchlist": significant_watchlist[:5],
            "significant_volume_rule": cboe_payload.get("significant_volume_rule", {}),
            "contracts": sorted(
                cboe_contracts,
                key=lambda item: int(dict(item).get("volume") or 0),
                reverse=True,
            )[:20],
            "last_non_empty_snapshot_available": latest_cboe_snapshot is not None,
        },
        "limitations": [
            "免费或未订阅行情可能延迟，页面必须同时查看数据时间。",
            "Cboe 高成交量榜至少延迟 20 分钟，只覆盖 Cboe 交易所且不是全美期权汇总。",
            "Cboe 榜单量只表示其榜单合约的成交量，不能单独证明异常活动或方向。",
            "成交量与未平仓量不能证明开仓、平仓或机构意图。",
            "方向标签只是报价位置推断，必须结合次日 OI、新闻及标的走势确认。",
            "Barchart 仅作人工 CSV 或原生邮件核对；LMIO 不抓取其网页。",
        ],
        "safety": {
            "can_trade": False,
            "paper_orders": False,
            "live_orders": False,
            "order_endpoint": False,
        },
    }


@app.get("/api/v1/options/board", tags=["research"])
def options_board() -> dict[str, object]:
    return _options_board_payload()


@app.get("/api/options/{symbol}", tags=["research"])
def options_by_symbol(symbol: str) -> dict[str, object]:
    normalised = symbol.strip().upper()
    if not normalised or len(normalised) > 10:
        raise HTTPException(status_code=422, detail="Invalid symbol.")
    return _options_board_payload(normalised)


@app.post(
    "/api/trade-plans",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def create_trade_plan(
    plan: ConditionalPlan,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    if plan.state is not PlanState.DRAFT:
        raise HTTPException(status_code=422, detail="New plans must start in DRAFT.")
    if not plan.market_snapshot_references:
        raise HTTPException(
            status_code=422,
            detail="A stored market snapshot reference is required.",
        )
    if plan.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Plan expiry must be in the future.")
    available_references = {
        f"provider_snapshots:{item['id']}"
        for item in get_service().store.history_json("provider_snapshots", 200)
    } | {
        f"news_price_confirmations:{item['id']}"
        for item in get_service().store.history_json("news_price_confirmations", 200)
    }
    missing_references = set(plan.market_snapshot_references) - available_references
    if missing_references:
        raise HTTPException(status_code=422, detail="Stored snapshot reference was not found.")
    plan = plan.model_copy(update={"created_by": principal.actor_id})
    payload = plan.model_dump(mode="json")
    record_id = get_service().store.append_json(
        "conditional_plans",
        {
            "symbol": plan.symbol,
            "state": plan.state,
            "version": plan.version,
            "payload": payload,
        },
    )
    audit_event("conditional_plan_created", symbol=plan.symbol, plan_id=record_id)
    return {"id": record_id, "plan": payload}


class PlanTransitionInput(BaseModel):
    target: PlanState
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


@app.post(
    "/api/trade-plans/{plan_id}/transition",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def transition_trade_plan(
    plan_id: int,
    payload: PlanTransitionInput,
    principal: Annotated[Principal, Depends(require_admin)],
) -> dict[str, Any]:
    record = next(
        (
            item
            for item in get_service().store.history_json("conditional_plans", 200)
            if item["id"] == plan_id
        ),
        None,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Trade plan not found.")
    plan = ConditionalPlan.model_validate(record["payload"])
    try:
        updated, event = transition_with_evidence(
            plan,
            payload.target,
            actor=principal.actor_id,
            reason=payload.reason,
            evidence_urls=payload.evidence_urls,
        )
    except (ValueError, PermissionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    event_payload = event.model_dump(mode="json")
    get_service().store.append_json(
        "trade_plan_transitions",
        {
            "symbol": event.symbol,
            "previous_state": event.previous_state,
            "new_state": event.new_state,
            "payload": event_payload,
        },
    )
    updated_id = get_service().store.append_json(
        "conditional_plans",
        {
            "symbol": updated.symbol,
            "state": updated.state,
            "version": updated.version,
            "payload": updated.model_dump(mode="json"),
        },
    )
    audit_event(
        "conditional_plan_transitioned",
        source_plan_id=plan_id,
        updated_plan_id=updated_id,
        symbol=event.symbol,
        previous_state=event.previous_state,
        new_state=event.new_state,
        actor=event.actor,
    )
    return {"id": updated_id, "event": event_payload}


@app.post(
    "/api/v1/reports/latest/telegram",
    tags=["reports"],
    dependencies=[Depends(require_admin)],
)
def deliver_latest_report() -> dict[str, str]:
    service = get_service()
    report = service.store.latest_json("reports")
    if report is None:
        raise HTTPException(status_code=404, detail="No report exists.")
    settings = get_settings()
    status = queue_or_send(
        service.store,
        str(report["message_zh"]),
        bot_token=settings.telegram_bot_token.get_secret_value(),
        chat_id=settings.telegram_chat_id.get_secret_value(),
    )
    audit_event("telegram_delivery_processed", status=status)
    return {"status": status}


@app.get("/", response_class=HTMLResponse, tags=["dashboard"])
def command_centre() -> str:
    report = get_service().store.latest_json("reports")
    if report is None:
        body = """
        <h1>Leon Market Intelligence OS</h1>
        <p class="muted">中文优先 · 美股研究与决策支持 · 不执行交易</p>
        <section><h2>尚无日报</h2><p>调用 <code>POST /api/v1/demo/run</code>
        生成明确标注的演示回放。</p></section>
        """
    else:
        service = get_service()
        provider_states = providers_health()
        provider_summary = "；".join(
            f"{name}={details['state']}" for name, details in provider_states.items()
        )
        urgent_events = [
            event
            for event in service.latest_news(limit=50)
            if event.get("significance", 0) >= 80 and event.get("confidence", 0) >= 0.7
        ][:5]
        top_rows = "".join(
            (
                "<tr>"
                f"<td>{escape(item['symbol'])}</td>"
                f"<td>{escape(item['company'])}</td>"
                f"<td>{escape(item['strategy'])}</td>"
                f"<td>{item['total_score']:.1f}</td>"
                f"<td>{item['scores']['confidence']:.0%}</td>"
                "</tr>"
            )
            for item in report["top_10"]
        )
        warnings = "".join(f"<li>{escape(item)}</li>" for item in report["warnings"])
        top_cards = "".join(
            (
                "<article>"
                f"<strong>{escape(item['symbol'])}｜{escape(item['strategy'])}</strong>"
                f"<p>{escape(item['what_changed'])}</p>"
                f"<p>确认：{escape(item['confirmation_condition'])}</p>"
                f"<p>失效：{escape(item['stop_reference'])}</p>"
                "</article>"
            )
            for item in report.get("decision_cards", [])
        )
        urgent = (
            "".join(f"<li>{escape(event['headline'])}</li>" for event in urgent_events)
            or "<li>无已验证 P0/P1 事件</li>"
        )
        risk_blocks = report["regime"].get("blocked_sectors", []) + report["regime"].get(
            "blocked_symbols", []
        )
        risk_text = "、".join(risk_blocks) if risk_blocks else "无主动封锁"
        body = f"""
        <h1>LMIO 指挥中心</h1>
        <p class="muted">中文优先 · 美股研究与决策支持 · 不执行交易</p>
        <div class="grid">
          <section><h2>市场状态</h2><strong>{escape(report["regime"]["label"])}</strong>
          <p>置信度 {report["regime"]["confidence"]:.0%}</p></section>
          <section><h2>每日漏斗</h2>
          <p>检查 {report["funnel"].get("universe_checked", 0)} 只股票</p>
          <p>基础范围 {report["funnel"].get("investable", 0)} 只 ·
          优先机会 {report["funnel"].get("priority_opportunities", 0)} 只</p></section>
          <section><h2>安全边界</h2><strong>不执行交易</strong>
          <p>实盘与模拟交易均关闭</p></section>
        </div>
        <div class="grid">
          <section><h2>数据新鲜度</h2><p>{escape(report["generated_at"])}</p>
          <p>模式：{escape(report["data_mode"])}</p></section>
          <section><h2>提供商状态</h2><p>{escape(provider_summary)}</p></section>
          <section><h2>下一计划事件</h2><p>按 Hermes 清单执行下一只读周期；未启用外部调度。</p>
          <p>风险封锁：{escape(risk_text)}</p></section>
        </div>
        <section><h2>Top 3 决策卡</h2><div class="grid">{top_cards or "<p>无合格项</p>"}</div>
        </section>
        <section><h2>P0 / P1 事件</h2><ul>{urgent}</ul></section>
        <section><h2>Top 10 观察名单</h2>
        <table><thead><tr><th>代码</th><th>公司</th><th>策略</th><th>总分</th>
        <th>数据置信度</th></tr></thead><tbody>{top_rows}</tbody></table></section>
        <section><h2>中文简报</h2><p>{escape(report["message_zh"])}</p>
        <ul>{warnings}</ul></section>
        """
    nav = " ".join(
        f'<a href="/dashboard/{slug}">{escape(label)}</a>'
        for slug, label in DASHBOARD_PAGES.items()
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>LMIO 指挥中心</title><style>
    body{{margin:0;background:#f5f5f2;color:#171717;font:16px/1.6 system-ui,sans-serif}}
    main{{max-width:1180px;margin:auto;padding:48px 24px}}h1{{font-size:clamp(2rem,5vw,4rem)}}
    nav{{display:flex;gap:14px;overflow:auto;padding:14px 0;border-bottom:1px solid #ccc}}
    nav a{{color:#171717;white-space:nowrap}}
    section{{background:white;border:1px solid #ddd;padding:24px;margin:20px 0}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
    .grid section{{margin:0}}.muted{{color:#5f6368}}table{{width:100%;border-collapse:collapse}}
    th,td{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}pre{{white-space:pre-wrap}}
    code{{background:#eee;padding:2px 5px}}@media(max-width:620px){{main{{padding:24px 14px}}
    table{{font-size:13px}}th:nth-child(2),td:nth-child(2){{display:none}}}}
    </style></head><body><main><nav>{nav}</nav>{body}</main></body></html>"""


@app.get("/dashboard/{page}", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_page(page: str) -> str:
    if page not in DASHBOARD_PAGES:
        raise HTTPException(status_code=404, detail="Unknown dashboard page.")
    service = get_service()
    report = service.store.latest_json("reports")
    if page == "command-centre":
        return command_centre()
    if page == "unusual-options":
        board = _options_board_payload()
        provider = dict(board["provider"])
        status = (
            f"已保存 {board['candidate_count']} 个异常活动候选；"
            f"数据源状态 {provider.get('state')}，交易执行保持关闭。"
        )
    elif page == "paper-trades":
        status = "CAN_TRADE、LIVE_TRADING_ENABLED 和 PAPER_TRADING_ENABLED 均为 false。"
    elif page == "intrinsic-value":
        valuations = service.store.history_json("valuation_runs")
        status = f"已保存 {len(valuations)} 个版本化估值运行；可通过 API 查看完整假设与敏感度。"
    elif page in {"top-10", "watchlists", "strategy-screener"}:
        count = len(report["top_10"]) if report else 0
        status = f"当前观察名单 {count} 项；每项保留策略、证据、四维评分和缺失字段。"
    elif page == "news-trading":
        status = f"已保存 {service.store.counts()['news_events']} 个去重官方事件。"
    elif page == "system-health":
        status = json_status(service.store.counts())
    elif page == "institutional-insider":
        count = service.store.counts()["ownership_events"]
        status = f"已保存 {count} 个版本化持仓事件；不以机构或内部人信息单独触发建议。"
    elif page == "conditional-plans":
        count = service.store.counts()["trade_plan_transitions"]
        status = (
            f"已保存 {count} 个状态转换证据。条件计划只用于研究确认；"
            "PAPER_READY / PAPER_OPEN 由安全配置阻止。"
        )
    elif page == "reports-journal":
        status = f"已保存 {service.store.counts()['reports']} 份版本化报告。"
    else:
        status = "所有敏感配置仅来自环境变量；页面不显示任何密钥。"
    nav = " ".join(
        f'<a href="/dashboard/{slug}">{escape(label)}</a>'
        for slug, label in DASHBOARD_PAGES.items()
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{escape(DASHBOARD_PAGES[page])} · LMIO</title><style>
    body{{margin:0;background:#f5f5f2;color:#171717;font:16px/1.6 system-ui,sans-serif}}
    main{{max-width:1100px;margin:auto;padding:40px 24px}}nav{{display:flex;gap:14px;overflow:auto;
    padding:14px 0;border-bottom:1px solid #ccc}}nav a{{color:#171717;white-space:nowrap}}
    section{{background:#fff;border:1px solid #ddd;padding:28px;margin-top:24px}}
    </style></head><body><main><nav>{nav}</nav><section>
    <p>LEON MARKET INTELLIGENCE OS</p><h1>{escape(DASHBOARD_PAGES[page])}</h1>
    <p>{escape(status)}</p><h2>如何使用</h2>
    <p>这是运行服务的简要诊断入口。日常研究请使用受保护的 LMIO 工作台，
    其中会以中文显示结论、评分、风险和下一步，而不会展示技术记录。</p>
    <p><a href="/">返回指挥中心</a></p>
    </section></main></body></html>"""


def json_status(value: dict[str, int]) -> str:
    return "；".join(f"{key}={count}" for key, count in value.items())
