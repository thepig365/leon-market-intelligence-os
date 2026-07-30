import json
from pathlib import Path


def test_hermes_manifest_cannot_schedule_trading() -> None:
    manifest = json.loads(Path("config/hermes_jobs.json").read_text())
    commands = " ".join(job["command"].lower() for job in manifest["jobs"])
    prohibited = {item.lower() for item in manifest["prohibited"]}

    assert manifest["orchestrator"] == "Hermes"
    assert all(job["mutates_external_state"] is False for job in manifest["jobs"])
    assert "trade" not in commands
    assert "order" not in commands
    assert "broker order execution" in prohibited
    assert "paper trading" in prohibited
    assert "live trading" in prohibited
