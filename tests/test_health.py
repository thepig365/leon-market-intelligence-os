from pathlib import Path

from lmio.config import Settings
from lmio.main import app, health
from lmio.service import LMIOService


def test_health_reports_hard_safety_state() -> None:
    assert health() == {
        "status": "ok",
        "service": "Leon Market Intelligence OS",
        "version": "1.0.0rc1",
        "environment": "test",
        "default_language": "zh-CN",
        "market": "US_EQUITIES",
        "can_trade": False,
        "live_trading_enabled": False,
        "paper_trading_enabled": False,
        "store_backend": "sqlite",
        "insecure_local_reads_enabled": False,
        "demo_mode_enabled": False,
        "release_sha": "unrecorded",
        "release_label": "LMIO v1.0 RC1 — Ready for Operator Acceptance",
    }


def test_service_readiness_does_not_claim_integrations_are_working(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=tmp_path / "test.sqlite3")
    service = LMIOService(settings)

    assert settings.integration_readiness() == {
        "sec_configured": False,
        "telegram_configured": False,
        "telegram_queries_configured": False,
        "finviz_configured": False,
        "scheduled_refresh_configured": False,
        "openai_research_configured": False,
        "admin_api_key_configured": False,
        "ibkr_bridge_configured": False,
        "read_api_key_configured": False,
    }
    assert service.store.counts()["reports"] == 0


def test_health_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/ready" in paths
    assert "/api/v1/demo/run" in paths
    assert "/api/v1/valuation/meta-acceptance" in paths
    assert "/dashboard/{page}" in paths
