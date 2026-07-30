from pathlib import Path

from lmio.config import Settings
from lmio.service import LMIOService


def test_daily_run_is_append_only_and_reproducible(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    first = service.run_demo_daily()
    second = service.run_demo_daily()
    counts = service.store.counts()

    assert first["top_10"] == second["top_10"]
    assert counts["universe_runs"] == 2
    assert counts["screen_runs"] == 2
    assert counts["reports"] == 2


def test_meta_valuation_is_versioned(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = service.run_meta_acceptance()

    assert result["symbol"] == "META"
    assert service.store.counts()["valuation_runs"] == 1
