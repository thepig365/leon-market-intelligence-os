"""Application orchestration for deterministic LMIO V1 workflows."""

import hashlib
import json

from lmio.candidates import transition_candidate
from lmio.config import Settings
from lmio.demo import demo_universe, meta_acceptance_input
from lmio.domain import (
    CandidateState,
    NewsEvent,
    ScreenCandidate,
    SecuritySnapshot,
    ValuationResult,
)
from lmio.reports import build_daily_report, classify_regime
from lmio.research import build_research_pack
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
        valuation = ValuationResult.model_validate(self.run_meta_acceptance())
        return self.run_daily(
            demo_universe(),
            data_mode="synthetic_replay",
            valuations={valuation.symbol: valuation},
        )

    def run_daily(
        self,
        snapshots: list[SecuritySnapshot],
        *,
        data_mode: str,
        valuations: dict[str, ValuationResult] | None = None,
    ) -> dict[str, object]:
        for snapshot in snapshots:
            snapshot_payload = snapshot.model_dump(mode="json")
            snapshot_fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "provider": data_mode,
                        "symbol": snapshot.symbol,
                        "observed_at": snapshot_payload["observed_at"],
                        "payload": snapshot_payload,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            self.store.put_provider_snapshot(
                snapshot_fingerprint,
                provider=data_mode,
                symbol=snapshot.symbol,
                company=snapshot.company,
                observed_at=str(snapshot_payload["observed_at"]),
                payload=snapshot_payload,
            )
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
        for candidate in candidates:
            evidence_urls = [
                item.source_url for item in candidate.evidence if item.source_url is not None
            ]
            transitions = [
                transition_candidate(
                    symbol=candidate.symbol,
                    strategy=candidate.strategy,
                    previous_state=CandidateState.DISCOVERED,
                    new_state=CandidateState.FILTERED,
                    reason="Deterministic strategy filter completed.",
                    actor="screening-agent",
                    evidence_urls=evidence_urls,
                )
            ]
            if candidate.state is CandidateState.RESEARCHING:
                transitions.append(
                    transition_candidate(
                        symbol=candidate.symbol,
                        strategy=candidate.strategy,
                        previous_state=CandidateState.FILTERED,
                        new_state=CandidateState.RESEARCHING,
                        reason="Data confidence requires additional research.",
                        actor="screening-agent",
                        evidence_urls=evidence_urls,
                    )
                )
            for transition in transitions:
                self.store.append_json(
                    "candidate_transitions",
                    {
                        "symbol": transition.symbol,
                        "strategy": transition.strategy,
                        "previous_state": transition.previous_state,
                        "new_state": transition.new_state,
                        "payload": transition.model_dump(mode="json"),
                    },
                )
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
            data_mode=data_mode,
            valuations=valuations,
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

    def research_latest(self, limit: int = 10) -> list[dict[str, object]]:
        latest = self.store.latest_json("screen_runs")
        if latest is None:
            raise ValueError("No screen run exists")
        news = [NewsEvent.model_validate(item) for item in self.store.news_payloads()]
        candidates = [ScreenCandidate.model_validate(item) for item in latest[:limit]]
        valuations: dict[str, ValuationResult] = {}
        for item in self.store.history_json("valuation_runs", 200):
            symbol = str(item["symbol"]).upper()
            if symbol not in valuations:
                valuations[symbol] = ValuationResult.model_validate(item["result_payload"])
        results: list[dict[str, object]] = []
        for candidate in candidates:
            pack = build_research_pack(
                candidate,
                news,
                valuations.get(candidate.symbol.upper()),
            )
            payload = pack.model_dump(mode="json")
            self.store.append_json(
                "research_packs",
                {
                    "symbol": pack.symbol,
                    "model_version": pack.model_version,
                    "payload": payload,
                },
            )
            results.append(payload)
        return results
