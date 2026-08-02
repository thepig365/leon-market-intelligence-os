import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lmio.config import Settings
from lmio.domain import NewsEvent, SecuritySnapshot
from lmio.main import DASHBOARD_PAGES, NewsAnalysisInput, analyse_news_event, app
from lmio.news import event_fingerprint
from lmio.news_price import ConfirmationState, NewsPriceConfirmation, PriceWindow
from lmio.service import LMIOService


def request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def perform() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)

    return asyncio.run(perform())


def test_health_and_dashboard_are_readable() -> None:
    response = request("GET", "/health")
    assert response.status_code == 200
    assert response.json()["can_trade"] is False

    dashboard = request("GET", "/")
    assert dashboard.status_code == 200
    assert "不执行交易" in dashboard.text


def test_runtime_read_key_protects_non_health_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        read_api_key="server-to-server-secret",
    )
    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)

    assert request("GET", "/health").status_code == 200
    assert request("GET", "/api/status").status_code == 401
    assert (
        request(
            "GET",
            "/api/status",
            headers={"x-lmio-read-key": "server-to-server-secret"},
        ).status_code
        == 200
    )


def test_ready_reports_latest_verified_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    service.store.append_json(
        "provider_health",
        {
            "provider": "finviz_elite_csv",
            "state": "ready",
            "payload": {"detail": "Authorised export parsed successfully."},
        },
    )
    monkeypatch.setattr("lmio.main.get_service", lambda: service)

    response = request("GET", "/ready")
    providers = request("GET", "/api/v1/providers/health")

    assert response.status_code == 200
    assert response.json()["provider_status"] == "ready"
    assert response.json()["latest_provider"]["provider"] == "finviz_elite_csv"
    assert providers.json()["finviz_elite_csv"]["state"] == "ready"


def test_command_centre_combines_operating_status_without_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        telegram_bot_token="123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        telegram_chat_id="8873919191",
        telegram_webhook_secret="webhook-secret",
        finviz_api_token="finviz-secret",
    )
    service = LMIOService(settings)
    service.store.append_json(
        "provider_health",
        {
            "provider": "finviz_elite_api",
            "state": "ready",
            "payload": {"detail": "Authorised API refresh completed."},
        },
    )
    service.store.append_json(
        "reports",
        {
            "report_type": "daily",
            "payload": {
                "generated_at": "2026-07-31T01:00:00Z",
                "data_mode": "authorised_finviz_api",
                "regime": {
                    "label": "Unverified",
                    "confidence": 0,
                    "blocked_sectors": [],
                    "blocked_symbols": [],
                },
                "funnel": {
                    "universe_checked": 5198,
                    "investable": 2854,
                    "abnormal_candidates": 752,
                },
                "top_10": [
                    {
                        "symbol": "SNDK",
                        "company": "Sandisk Corp",
                        "strategy": "pattern_recognition",
                        "total_score": 70,
                    }
                ],
                "top_3": [],
                "warnings": [],
            },
        },
    )
    monkeypatch.setattr("lmio.main.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.main.get_service", lambda: service)

    response = request("GET", "/api/v1/command-centre")

    assert response.status_code == 200
    payload = response.json()
    assert payload["research_queue"][0]["symbol"] == "SNDK"
    assert payload["provider_health"]["finviz_elite_api"]["state"] == "ready"
    assert payload["telegram"]["private_queries_configured"] is True
    assert payload["safety"] == {
        "can_trade": False,
        "live_trading_enabled": False,
        "paper_trading_enabled": False,
    }
    assert "finviz-secret" not in response.text
    assert "webhook-secret" not in response.text


def test_all_dashboard_pages_exist() -> None:
    for page in DASHBOARD_PAGES:
        response = request("GET", f"/dashboard/{page}")
        assert response.status_code == 200, page


def test_mutating_api_is_closed_without_admin_key() -> None:
    response = request("POST", "/api/v1/demo/run")

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]

    news_analysis = request("POST", "/api/news/unknown/analyse")
    assert news_analysis.status_code == 503


def test_synthetic_replay_is_disabled_even_for_admin_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        admin_api_key="admin-secret",
        read_api_key="read-secret",
    )
    monkeypatch.setattr("lmio.main.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)

    response = request(
        "POST",
        "/api/v1/demo/run",
        headers={
            "x-lmio-key": "admin-secret",
            "x-lmio-read-key": "read-secret",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Synthetic replay is disabled."


def test_scheduled_finviz_refresh_requires_cron_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cron_secret="scheduled-test-key",
    )

    class RefreshService:
        def refresh_finviz(self, **_kwargs: object) -> dict[str, object]:
            return {
                "status": "completed",
                "provider": "finviz_elite_api",
                "equities_received": 100,
                "candidates_found": 10,
                "telegram": "sent",
                "generated_at": "2026-07-31T01:00:00Z",
            }

    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.main.get_service", RefreshService)

    denied = request("GET", "/api/v1/providers/finviz/refresh")
    allowed = request(
        "GET",
        "/api/v1/providers/finviz/refresh",
        headers={"authorization": "Bearer scheduled-test-key"},
    )
    preview_allowed = request(
        "GET",
        "/api/v1/providers/finviz/refresh",
        headers={"x-lmio-cron-key": "scheduled-test-key"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert preview_allowed.status_code == 200
    assert allowed.json()["telegram"] == "sent"


def test_scheduled_news_refresh_requires_cron_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cron_secret="scheduled-test-key",
    )

    class RefreshService:
        def refresh_official_news(self) -> dict[str, object]:
            return {
                "macro": {"feeds": 5, "failed_feeds": 0, "checked": 10, "inserted": 2},
                "sec": {"symbols": 12, "checked": 20, "inserted": 1},
            }

    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.main.get_service", RefreshService)

    denied = request("GET", "/api/v1/providers/news/refresh")
    allowed = request(
        "GET",
        "/api/v1/providers/news/refresh",
        headers={"authorization": "Bearer scheduled-test-key"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["macro"]["failed_feeds"] == 0


def test_telegram_webhook_only_answers_leons_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        telegram_bot_token="123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        telegram_chat_id="8873919191",
        telegram_webhook_secret="webhook-secret",
        finviz_api_token="private-token",
    )
    snapshot = SecuritySnapshot(
        symbol="SNDK",
        company="Sandisk Corp",
        source="finviz_elite_api",
        price=44,
        market_cap_m=20_000,
        average_dollar_volume_m=100,
        relative_volume=1.2,
        rsi_14=55,
        chart_pattern="Channel Up",
    )

    class TelegramService:
        store = object()

        def finviz_symbol_snapshot(self, symbol: str) -> SecuritySnapshot | None:
            return snapshot if symbol == "SNDK" else None

    deliveries: list[str] = []
    monkeypatch.setattr("lmio.main.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)
    monkeypatch.setattr("lmio.main.get_service", lambda: TelegramService())
    monkeypatch.setattr(
        "lmio.main.queue_or_send",
        lambda _store, message, **_kwargs: deliveries.append(message) or "sent",
    )

    denied = request(
        "POST",
        "/api/v1/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "wrong"},
        json={"message": {"chat": {"id": 8873919191}, "text": "SNDK"}},
    )
    ignored = request(
        "POST",
        "/api/v1/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "webhook-secret"},
        json={"message": {"chat": {"id": 1}, "text": "SNDK"}},
    )
    accepted = request(
        "POST",
        "/api/v1/telegram/webhook",
        headers={"x-telegram-bot-api-secret-token": "webhook-secret"},
        json={"message": {"chat": {"id": 8873919191}, "text": "SNDK"}},
    )

    assert denied.status_code == 403
    assert ignored.json()["status"] == "ignored"
    assert accepted.json() == {"status": "accepted", "delivery": "sent"}
    assert "SNDK Finviz 快照" in deliveries[0]


def test_read_only_research_api_surface_is_available() -> None:
    paths = (
        "/api/v1/candidates",
        "/api/v1/research",
        "/api/v1/news",
        "/api/v1/ownership",
        "/api/v1/plans",
        "/api/v1/signals",
        "/api/v1/performance",
        "/api/v1/watchlists",
    )

    for path in paths:
        response = request("GET", path)
        assert response.status_code == 200, path


def test_latest_screen_returns_persisted_candidate_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    service.store.append_json(
        "screen_runs",
        {
            "calculation_version": "screens-v1",
            "universe_run_id": None,
            "payload": [{"symbol": "TEST", "strategy": "quality_growth_momentum"}],
        },
    )
    monkeypatch.setattr("lmio.main.get_service", lambda: service)

    response = request("GET", "/api/v1/screens/latest")

    assert response.status_code == 200
    assert response.json() == [{"symbol": "TEST", "strategy": "quality_growth_momentum"}]


def test_feedback_write_is_protected() -> None:
    response = request(
        "POST",
        "/api/v1/feedback",
    )

    assert response.status_code == 503


def test_watchlist_history_binds_actor_to_authenticated_principal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        admin_api_key="admin-secret",
        owner_identity="leon-owner",
    )
    service = LMIOService(settings)
    monkeypatch.setattr("lmio.main.get_service", lambda: service)
    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)

    created = request(
        "POST",
        "/api/v1/watchlists",
        headers={"x-lmio-key": "admin-secret"},
        json={
            "name": "Priority research",
            "reason": "Verified screen requires review.",
            "evidence_urls": ["https://example.test/evidence"],
        },
    )
    member = request(
        "POST",
        f"/api/v1/watchlists/{created.json()['id']}/members",
        headers={"x-lmio-key": "admin-secret"},
        json={
            "symbol": "test",
            "action": "add",
            "reason": "Meets current screen.",
            "evidence_urls": ["https://example.test/evidence"],
        },
    )

    assert created.status_code == 200
    assert member.status_code == 200
    history = service.store.history_json("watchlist_members")
    assert history[0]["payload"]["actor"] == "leon-owner"
    assert history[0]["payload"]["version"] == 1


def test_master_spec_api_surface_is_present() -> None:
    required = {
        "/api/status",
        "/api/providers/health",
        "/api/market/regime",
        "/api/market/premarket-brief",
        "/api/screens/run",
        "/api/screens",
        "/api/screens/{run_id}/results",
        "/api/candidates",
        "/api/candidates/{symbol}",
        "/api/candidates/{symbol}/research",
        "/api/candidates/{symbol}/feedback",
        "/api/valuation/{symbol}/run",
        "/api/valuation/{symbol}/latest",
        "/api/valuation/{symbol}/history",
        "/api/news/events",
        "/api/news/check",
        "/api/news/{event_id}/analyse",
        "/api/institutions/{symbol}",
        "/api/insiders/{symbol}",
        "/api/options/{symbol}",
        "/api/trade-plans",
        "/api/trade-plans/{plan_id}/transition",
        "/api/reports",
        "/api/strategy-performance",
        "/api/v1/providers/news/refresh",
    }

    assert required <= set(app.openapi()["paths"])


def test_news_analysis_creates_only_a_conditional_draft(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    event = NewsEvent(
        headline="Company raises official guidance",
        source="Company IR",
        source_url="https://example.test/investor-relations/guidance",
        source_tier=1,
        published_at=datetime(2026, 7, 30, tzinfo=UTC),
        symbols=["TEST"],
        event_type="guidance",
        significance=90,
        surprise=25,
        confidence=0.95,
    )
    fingerprint = event_fingerprint(event)
    service.store.put_news_event(fingerprint, event.model_dump(mode="json"))
    observed = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)
    confirmation = NewsPriceConfirmation(
        original_source=event.source,
        source_url=event.source_url,
        publication_time=event.published_at,
        ingestion_time=observed,
        event_type=event.event_type,
        affected_symbols=event.symbols,
        significance=event.significance,
        source_quality=event.source_tier,
        event_specific_explanation="Official guidance increased.",
        expected_transmission_mechanism="Higher expected earnings.",
        pre_event_price=100,
        post_event_price_windows=[
            PriceWindow(
                observed_at=observed,
                price=103,
                benchmark_price=100,
                relative_volume=1.5,
                vwap=101,
                opening_range_high=102,
                opening_range_low=99,
            )
        ],
        abnormal_return_vs_benchmark=0.03,
        relative_volume=1.5,
        vwap_position="above",
        opening_range_behaviour="breakout_above",
        gap_retention="positive",
        confirmation_state=ConfirmationState.CONFIRMED,
        invalidation_state="active",
        next_review_time=None,
    )
    service.store.append_json(
        "news_price_confirmations",
        {"symbol": "TEST", "state": "confirmed", "payload": confirmation.model_dump(mode="json")},
    )
    monkeypatch.setattr("lmio.main.get_service", lambda: service)

    result = analyse_news_event(
        fingerprint,
        NewsAnalysisInput(),
    )

    assert result["conditional_plan"]["state"] == "draft"
    assert result["order_created"] is False
    assert service.store.counts()["conditional_plans"] == 1


def test_news_analysis_does_not_accept_client_price_reaction() -> None:
    assert "reaction" not in NewsAnalysisInput.model_fields
