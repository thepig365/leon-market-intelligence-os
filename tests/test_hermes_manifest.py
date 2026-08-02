import json
from pathlib import Path

from lmio.scheduler import load_scheduler_manifest, next_scheduled_time


def test_scheduler_manifest_maps_every_required_purpose_to_safe_code() -> None:
    manifest = json.loads(Path("config/scheduler_manifest.json").read_text())
    commands = " ".join(job["command"].lower() for job in manifest["jobs"])
    prohibited = {item.lower() for item in manifest["prohibited"]}

    assert {job["id"] for job in manifest["jobs"]} == {
        "premarket-data-screening",
        "after-open-finviz-refresh",
        "after-close-outcomes-report",
        "official-news-refresh",
        "sec-refresh",
        "telegram-outbox-drain",
        "weekend-strategy-data-quality-review",
    }
    assert all("python -m lmio.cli scheduled-job" in job["command"] for job in manifest["jobs"])
    assert "trade" not in commands
    assert "order" not in commands
    assert "broker order execution" in prohibited
    assert "paper trading" in prohibited
    assert "live trading" in prohibited

    jobs = load_scheduler_manifest()
    assert all(next_scheduled_time(job).tzinfo is not None for job in jobs)
