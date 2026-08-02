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
        "broker_package_absent": True,
        "order_endpoint_absent": True,
    }
    assert health["freshness"]["market_snapshot"]["freshness_state"] == "unknown"
