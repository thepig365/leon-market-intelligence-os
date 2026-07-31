import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lmio.config import Settings
from lmio.domain import NewsEvent
from lmio.main import DASHBOARD_PAGES, NewsAnalysisInput, analyse_news_event, app
from lmio.news import event_fingerprint
from lmio.news_plan import ReactionEvidence
from lmio.service import LMIOService


def request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def perform() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers)

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
    monkeypatch.setattr("lmio.main.get_service", lambda: service)

    result = analyse_news_event(
        fingerprint,
        NewsAnalysisInput(
            reaction=ReactionEvidence(
                window_minutes=30,
                stock_return_pct=2,
                benchmark_return_pct=0,
                relative_volume=1.5,
                vwap_confirmed=True,
                opening_range_confirmed=True,
            )
        ),
    )

    assert result["conditional_plan"]["state"] == "draft"
    assert result["order_created"] is False
    assert service.store.counts()["conditional_plans"] == 1
