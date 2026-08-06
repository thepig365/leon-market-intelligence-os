from datetime import UTC, datetime
from pathlib import Path

from lmio.config import Settings
from lmio.health_console import build_system_health
from lmio.service import LMIOService


def test_system_health_is_truthful_when_no_pipeline_or_data_exists(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3")
    service = LMIOService(settings)

    health = build_system_health(service.store, settings)

    assert health["status"] == "degraded"
    assert health["pipeline"]["status"] == "never_run"
    assert health["application"]["scheduler"]["manifest_loaded"] is True
    assert health["application"]["scheduler"]["executor_process"] == "not_verified"
    assert health["safety"] == {
        "CAN_TRADE": False,
        "LIVE_TRADING_ENABLED": False,
        "PAPER_TRADING_ENABLED": False,
        "ibkr_bridge_configured": False,
        "order_adapter_enabled": False,
        "order_endpoint_absent": True,
    }
    assert health["freshness"]["market_snapshot"]["freshness_state"] == "unknown"


def test_system_health_exposes_safe_current_ibkr_paper_status(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        ibkr_bridge_key="configured",
    )
    service = LMIOService(settings)
    service.store.append_json(
        "provider_health",
        {
            "provider": "ibkr_tws_paper",
            "state": "ready",
            "payload": {
                "observed_at": datetime.now(UTC).isoformat(),
                "connected": True,
                "paper_account_confirmed": True,
                "paper_order_permission_confirmed": True,
                "news_providers": [{"code": "DJNL", "name": "Dow Jones Newsletters"}],
                "headline_probe_count": 0,
                "data_scope": "status_and_provider_metadata_only",
            },
        },
    )

    health = build_system_health(service.store, settings)
    ibkr = health["providers"]["ibkr_tws_paper"]
    assert ibkr["connected"] is True
    assert ibkr["paper_account_confirmed"] is True
    assert ibkr["news_provider_names"] == ["Dow Jones Newsletters"]
    assert "account_id" not in str(ibkr)
    assert health["safety"]["order_adapter_enabled"] is False
