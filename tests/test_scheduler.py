from pathlib import Path

from lmio.config import Settings
from lmio.scheduler import run_scheduled_job, scheduler_status
from lmio.service import LMIOService


def test_weekend_job_executes_and_persists_truthful_history(tmp_path: Path) -> None:
    service = LMIOService(
        Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3")
    )

    result = run_scheduled_job(service, "weekend-strategy-data-quality-review")
    status = scheduler_status(service.store)

    assert result["status"] == "succeeded"
    weekend = next(
        item for item in status["jobs"] if item["id"] == "weekend-strategy-data-quality-review"
    )
    assert weekend["last_status"] == "succeeded"
    assert weekend["last_run"] is not None
