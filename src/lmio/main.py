"""LMIO FastAPI application and local read-only command centre."""

import json
from functools import lru_cache
from html import escape
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from lmio import __version__
from lmio.audit import audit_event
from lmio.config import get_settings
from lmio.plans import ConditionalPlan, PlanState, transition_with_evidence
from lmio.security import require_admin
from lmio.service import LMIOService
from lmio.telegram import queue_or_send

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
    "unusual-options": "异常期权（延后）",
    "paper-trades": "模拟交易（关闭）",
}


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


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/ready", tags=["system"])
def ready() -> dict[str, Any]:
    settings = get_settings()
    service = get_service()
    payload = health_payload()
    payload["integrations"] = settings.integration_readiness()
    payload["provider_status"] = (
        "configured_not_verified"
        if any(settings.integration_readiness().values())
        else "not_configured"
    )
    payload["store"] = {"status": "ready", "counts": service.store.counts()}
    audit_event("readiness_checked", environment=payload["environment"])
    return payload


@app.get("/api/status", tags=["system"])
def api_status() -> dict[str, Any]:
    return ready()


@app.get("/api/v1/providers/health", tags=["system"])
def providers_health() -> dict[str, Any]:
    readiness = get_settings().integration_readiness()
    return {
        name.removesuffix("_configured"): {
            "state": "configured_not_verified" if configured else "disabled",
        }
        for name, configured in readiness.items()
    }


app.get("/api/providers/health", tags=["system"])(providers_health)


@app.post("/api/v1/demo/run", tags=["research"], dependencies=[Depends(require_admin)])
def run_demo() -> dict[str, object]:
    audit_event("synthetic_daily_run_started")
    return get_service().run_demo_daily()


@app.get("/api/v1/reports/latest", tags=["research"])
def latest_report() -> dict[str, Any]:
    report = get_service().store.latest_json("reports")
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No report exists. Run the synthetic replay first.",
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
def latest_screen() -> dict[str, Any]:
    screen = get_service().store.latest_json("screen_runs")
    if screen is None:
        raise HTTPException(status_code=404, detail="No screen run exists.")
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
    return get_service().store.news_payloads(limit)


@app.get("/api/v1/ownership", tags=["research"])
def ownership_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("ownership_events", limit)


@app.get("/api/v1/plans", tags=["research"])
def plan_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("conditional_plans", limit)


@app.get("/api/v1/signals", tags=["research"])
def signal_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("signals", limit)


@app.get("/api/v1/performance", tags=["research"])
def performance_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("strategy_performance", limit)


@app.get("/api/v1/watchlists", tags=["research"])
def watchlist_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("watchlists", limit)


class FeedbackInput(BaseModel):
    subject_type: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1, max_length=120)
    decision: str = Field(pattern="^(approved|rejected|needs_revision)$")
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


@app.post(
    "/api/v1/feedback",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def record_feedback(payload: FeedbackInput) -> dict[str, Any]:
    record = payload.model_dump(mode="json")
    record_id = get_service().store.append_json(
        "user_feedback",
        {
            "subject_type": payload.subject_type,
            "subject_id": payload.subject_id,
            "decision": payload.decision,
            "actor": payload.actor,
            "payload": record,
        },
    )
    audit_event(
        "user_feedback_recorded",
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        decision=payload.decision,
        actor=payload.actor,
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
def candidate_feedback(symbol: str, payload: FeedbackInput) -> dict[str, Any]:
    if payload.subject_id.upper() != symbol.upper():
        raise HTTPException(status_code=422, detail="Feedback subject does not match symbol.")
    return record_feedback(payload)


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


@app.get("/api/options/{symbol}", tags=["deferred"])
def deferred_options(symbol: str) -> dict[str, str]:
    raise HTTPException(
        status_code=409,
        detail=f"Options flow is deferred in V1; no provider is active for {symbol.upper()}.",
    )


@app.post(
    "/api/trade-plans",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def create_trade_plan(plan: ConditionalPlan) -> dict[str, Any]:
    if plan.state is not PlanState.DRAFT:
        raise HTTPException(status_code=422, detail="New plans must start in DRAFT.")
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
    actor: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)


@app.post(
    "/api/trade-plans/{plan_id}/transition",
    tags=["research"],
    dependencies=[Depends(require_admin)],
)
def transition_trade_plan(plan_id: int, payload: PlanTransitionInput) -> dict[str, Any]:
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
            actor=payload.actor,
            reason=payload.reason,
            evidence_urls=payload.evidence_urls,
            paper_trading_enabled=False,
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
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
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
            for event in service.store.news_payloads(limit=50)
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
          <section><h2>每日漏斗</h2><pre>{escape(str(report["funnel"]))}</pre></section>
          <section><h2>安全边界</h2><strong>CAN_TRADE = false</strong>
          <p>LIVE / PAPER 均关闭</p></section>
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
        <section><h2>中文简报</h2><pre>{escape(report["message_zh"])}</pre>
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
    details: object = []
    if page in {"unusual-options", "paper-trades"}:
        status = (
            "V1 延后模块，未配置数据提供商。"
            if page == "unusual-options"
            else "CAN_TRADE、LIVE_TRADING_ENABLED 和 PAPER_TRADING_ENABLED 均为 false。"
        )
    elif page == "intrinsic-value":
        valuations = service.store.history_json("valuation_runs")
        status = f"已保存 {len(valuations)} 个版本化估值运行；可通过 API 查看完整假设与敏感度。"
        details = valuations[:10]
    elif page in {"top-10", "watchlists", "strategy-screener"}:
        count = len(report["top_10"]) if report else 0
        status = f"当前观察名单 {count} 项；每项保留策略、证据、四维评分和缺失字段。"
        details = report["top_10"] if report else []
    elif page == "news-trading":
        status = f"已保存 {service.store.counts()['news_events']} 个去重官方事件。"
        details = service.store.news_payloads(limit=20)
    elif page == "system-health":
        status = json_status(service.store.counts())
        details = health_payload()
    elif page == "institutional-insider":
        count = service.store.counts()["ownership_events"]
        status = f"已保存 {count} 个版本化持仓事件；不以机构或内部人信息单独触发建议。"
        details = service.store.history_json("ownership_events", 20)
    elif page == "conditional-plans":
        count = service.store.counts()["trade_plan_transitions"]
        status = (
            f"已保存 {count} 个状态转换证据。条件计划只用于研究确认；"
            "PAPER_READY / PAPER_OPEN 由安全配置阻止。"
        )
        details = service.store.history_json("trade_plan_transitions", 20)
    elif page == "reports-journal":
        status = f"已保存 {service.store.counts()['reports']} 份版本化报告。"
        details = service.store.history_json("reports", 10)
    else:
        status = "所有敏感配置仅来自环境变量；页面不显示任何密钥。"
        details = get_settings().public_health()
    nav = " ".join(
        f'<a href="/dashboard/{slug}">{escape(label)}</a>'
        for slug, label in DASHBOARD_PAGES.items()
    )
    evidence = escape(json.dumps(details, ensure_ascii=False, indent=2, default=str))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{escape(DASHBOARD_PAGES[page])} · LMIO</title><style>
    body{{margin:0;background:#f5f5f2;color:#171717;font:16px/1.6 system-ui,sans-serif}}
    main{{max-width:1100px;margin:auto;padding:40px 24px}}nav{{display:flex;gap:14px;overflow:auto;
    padding:14px 0;border-bottom:1px solid #ccc}}nav a{{color:#171717;white-space:nowrap}}
    section{{background:#fff;border:1px solid #ddd;padding:28px;margin-top:24px}}
    pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f7f5;padding:18px}}
    </style></head><body><main><nav>{nav}</nav><section>
    <p>LEON MARKET INTELLIGENCE OS</p><h1>{escape(DASHBOARD_PAGES[page])}</h1>
    <p>{escape(status)}</p><h2>运行证据</h2><pre>{evidence}</pre>
    <p><a href="/">返回指挥中心</a></p>
    </section></main></body></html>"""


def json_status(value: dict[str, int]) -> str:
    return "；".join(f"{key}={count}" for key, count in value.items())
