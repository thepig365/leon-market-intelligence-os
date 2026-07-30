"""LMIO FastAPI application and local read-only command centre."""

from functools import lru_cache
from html import escape
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from lmio import __version__
from lmio.audit import audit_event
from lmio.config import get_settings
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


@app.get("/api/v1/providers/health", tags=["system"])
def providers_health() -> dict[str, Any]:
    readiness = get_settings().integration_readiness()
    return {
        name.removesuffix("_configured"): {
            "state": "configured_not_verified" if configured else "disabled",
        }
        for name, configured in readiness.items()
    }


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


@app.get("/api/v1/screens/latest", tags=["research"])
def latest_screen() -> dict[str, Any]:
    screen = get_service().store.latest_json("screen_runs")
    if screen is None:
        raise HTTPException(status_code=404, detail="No screen run exists.")
    return screen


@app.get("/api/v1/reports/history", tags=["research"])
def report_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("reports", limit)


@app.get("/api/v1/valuations/history", tags=["valuation"])
def valuation_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_service().store.history_json("valuation_runs", limit)


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
    if page in {"unusual-options", "paper-trades"}:
        status = (
            "V1 延后模块，未配置数据提供商。"
            if page == "unusual-options"
            else "CAN_TRADE、LIVE_TRADING_ENABLED 和 PAPER_TRADING_ENABLED 均为 false。"
        )
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
        status = "基础解析模块待数据源验证；不以机构或内部人信息单独触发建议。"
    elif page == "conditional-plans":
        status = "条件计划仅用于研究确认、失效和到期状态；不存在订单执行路径。"
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
    <p>{escape(status)}</p><p><a href="/">返回指挥中心</a></p>
    </section></main></body></html>"""


def json_status(value: dict[str, int]) -> str:
    return "；".join(f"{key}={count}" for key, count in value.items())
