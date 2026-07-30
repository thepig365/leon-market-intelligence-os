"""Application orchestration for deterministic LMIO V1 workflows."""

import hashlib
import json

from lmio.config import Settings
from lmio.demo import demo_universe, meta_acceptance_input
from lmio.reports import build_daily_report, classify_regime
from lmio.screens import run_core_screens
from lmio.store import RuntimeStore
from lmio.universe import UniversePolicy, build_investable_universe
from lmio.valuation import run_valuation


class LMIOService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = RuntimeStore(settings.database_path)
        self.store.migrate()

    def run_demo_daily(self) -> dict[str, object]:
        snapshots = demo_universe()
        policy = UniversePolicy()
        investable = build_investable_universe(snapshots, policy)
        serialised = [item.model_dump(mode="json") for item in investable]
        input_hash = hashlib.sha256(json.dumps(serialised, sort_keys=True).encode()).hexdigest()
        universe_id = self.store.append_json(
            "universe_runs",
            {
                "policy_version": policy.version,
                "input_count": len(snapshots),
                "investable_count": len(investable),
                "input_hash": input_hash,
                "payload": serialised,
            },
        )
        candidates = run_core_screens(investable)
        self.store.append_json(
            "screen_runs",
            {
                "calculation_version": "screens-v1",
                "universe_run_id": universe_id,
                "payload": [item.model_dump(mode="json") for item in candidates],
            },
        )
        regime = classify_regime(0.7, 1.0, 0.4, 17.5, 58)
        report = build_daily_report(
            candidates,
            universe_checked=len(snapshots),
            investable=len(investable),
            regime=regime,
            data_mode="synthetic_replay",
        )
        self.store.append_json(
            "reports",
            {"report_type": "daily", "payload": report.model_dump(mode="json")},
        )
        return report.model_dump(mode="json")

    def run_meta_acceptance(self) -> dict[str, object]:
        data = meta_acceptance_input()
        result = run_valuation(data)
        self.store.append_json(
            "valuation_runs",
            {
                "symbol": data.symbol,
                "calculation_version": result.calculation_version,
                "input_payload": data.model_dump(mode="json"),
                "result_payload": result.model_dump(mode="json"),
            },
        )
        return result.model_dump(mode="json")
