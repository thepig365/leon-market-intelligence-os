from pathlib import Path

from lmio.pipeline import OperationalPipeline, StageResult, StageStatus
from lmio.store import RuntimeStore


def _store(tmp_path: Path) -> RuntimeStore:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()
    return store


def test_pipeline_persists_one_run_and_all_22_stage_outcomes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handlers = {
        order: (lambda context, order=order: StageResult(
            output_count=order,
            evidence_references=[f"evidence:{context['run_id']}:{order}"],
        ))
        for order in range(1, 23)
    }

    result = OperationalPipeline(store, handlers).run()

    assert result["status"] == "succeeded"
    assert len(result["stages"]) == 22
    runs = store.history_json("pipeline_runs")
    stages = store.history_json("pipeline_stages", 50)
    assert len(runs) == 1
    assert len(stages) == 22
    assert {stage["run_id"] for stage in stages} == {result["run_id"]}


def test_failed_market_snapshot_blocks_misleading_downstream_output(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def fail_market(_: dict[str, object]) -> StageResult:
        return StageResult(status=StageStatus.FAILED, error_summary="ProviderUnavailable")

    handlers = {
        1: lambda _: StageResult(status=StageStatus.SUCCEEDED),
        2: fail_market,
        5: lambda _: StageResult(output_count=10),
        9: lambda _: StageResult(output_count=10),
        16: lambda _: StageResult(output_count=1),
        21: lambda _: StageResult(
            status=StageStatus.PARTIAL,
            warning_count=1,
            evidence_references=["health:degraded"],
        ),
    }

    result = OperationalPipeline(store, handlers).run()
    statuses = {stage["stage_order"]: stage["status"] for stage in result["stages"]}

    assert result["status"] == "failed"
    assert result["blocking_stage"] == 2
    assert statuses[2] == "failed"
    assert statuses[5] == "blocked"
    assert statuses[9] == "blocked"
    assert statuses[16] == "blocked"
    assert statuses[21] == "partial"
