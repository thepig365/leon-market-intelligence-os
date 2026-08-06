from datetime import UTC, datetime
from pathlib import Path

import httpx

from lmio.config import Settings
from lmio.domain import DataProvenance
from lmio.pipeline import OperationalPipeline, StageResult, StageStatus
from lmio.providers.finviz_api import FINVIZ_EXPORT_URL, FinvizAPIProvider
from lmio.service import LMIOService
from lmio.store import RuntimeStore
from lmio.valuation_inputs import FinancialEvidence


def _store(tmp_path: Path) -> RuntimeStore:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()
    return store


def test_pipeline_persists_one_run_and_all_21_stage_outcomes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    handlers = {
        order: (
            lambda context, order=order: StageResult(
                output_count=order,
                evidence_references=[f"evidence:{context['run_id']}:{order}"],
            )
        )
        for order in range(1, 22)
    }

    result = OperationalPipeline(store, handlers).run()

    assert result["status"] == "succeeded"
    assert len(result["stages"]) == 21
    runs = store.history_json("pipeline_runs")
    stages = store.history_json("pipeline_stages", 50)
    assert len(runs) == 1
    assert len(stages) == 21
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


def test_operational_run_persists_same_run_valuation_research_and_lineage(
    tmp_path: Path, monkeypatch
) -> None:
    header = (
        "Ticker,Company,Sector,Industry,Country,Exchange,Market Cap,Forward P/E,"
        "EPS Growth Quarter Over Quarter,Sales Growth Quarter Over Quarter,Gross Margin,"
        "Operating Margin,Return on Invested Capital,Total Debt/Equity,"
        "Performance (Half Year),200-Day Simple Moving Average,EPS Surprise,"
        "Relative Volume,Average Volume,Volume,Price,Relative Strength Index (14),"
        "Institutional Transactions,Short Float,Short Ratio\n"
    )
    row = (
        "TEST,Test Inc,Technology,Software - Application,USA,NASD,2500,20,25%,15%,60%,"
        "20%,18%,0.5,12%,8%,6%,1.4,1500,2000000,40,55,3%,16%,4\n"
    )

    def transport(_url: str, _params: dict[str, str], _timeout: float) -> httpx.Response:
        return httpx.Response(
            200,
            content=(header + row).encode(),
            headers={"content-type": "text/csv"},
            request=httpx.Request("GET", FINVIZ_EXPORT_URL),
        )

    provider = FinvizAPIProvider("private-token", transport=transport)
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    monkeypatch.setattr(
        service,
        "refresh_official_news",
        lambda: {
            "macro": {"status": "completed", "stored": 0, "failed_feeds": 0},
            "sec": {"status": "disabled"},
        },
    )
    evidence = FinancialEvidence(
        symbol="TEST",
        company_type="mature_non_financial",
        provenance=DataProvenance.LIVE_AUTHORISED,
        observed_at=datetime.now(UTC),
        source_fields={
            "operating_cash_flow": 100,
            "capex": 30,
            "net_cash": 20,
            "diluted_shares": 10,
            "market_price": 40,
        },
        source_references={
            "operating_cash_flow": "https://example.test/filing",
            "market_price": "https://example.test/market",
        },
        assumptions={
            "growth_rate": 0.08,
            "terminal_growth": 0.03,
            "discount_rate": 0.1,
            "forecast_years": 5,
        },
    )

    result = service.run_operational_pipeline(
        finviz_provider=provider,
        valuation_evidence_by_symbol={"TEST": evidence},
    )

    run_id = str(result["run_id"])
    assert all(item["run_id"] == run_id for item in service.store.history_json("top10_rankings"))
    assert all(
        item["run_id"] == run_id for item in service.store.history_json("valuation_input_records")
    )
    valuation = service.store.history_json("valuation_runs", 1)[0]
    assert valuation["input_payload"]["run_id"] == run_id
    research = service.store.history_json("research_packs", 1)[0]["payload"]
    assert research["run_id"] == run_id
    assert research["candidate_id"]
    lineage = service.store.history_json("operational_lineage", 1)[0]
    assert lineage["run_id"] == run_id
    assert lineage["payload"]["report_id"].startswith("report-")
