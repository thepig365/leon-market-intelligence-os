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
from lmio.providers.finviz_api import FinvizAPIProvider
from lmio.reports import build_daily_report, classify_regime, unverified_regime
from lmio.research import build_research_pack
from lmio.screens import run_core_screens
from lmio.store import RuntimeStore
from lmio.supabase_store import SupabaseRuntimeStore
from lmio.telegram import MessageKind, queue_or_send
from lmio.universe import UniversePolicy, build_investable_universe
from lmio.valuation import run_valuation

MAX_OPERATIONAL_CANDIDATES = 50


class LMIOService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.store_backend == "supabase":
            self.store = SupabaseRuntimeStore(
                settings.supabase_url,
                settings.supabase_service_role_key.get_secret_value(),
            )
        else:
            self.store = RuntimeStore(settings.database_path)
        self.store.migrate()

    def run_demo_daily(self) -> dict[str, object]:
        valuation = ValuationResult.model_validate(self.run_meta_acceptance())
        return self.run_daily(
            demo_universe(),
            data_mode="synthetic_replay",
            valuations={valuation.symbol: valuation},
        )

    def refresh_finviz(
        self,
        *,
        provider: FinvizAPIProvider | None = None,
        message_kind: MessageKind = MessageKind.PREMARKET,
    ) -> dict[str, object]:
        """Refresh authorised Finviz data and deliver one concise Telegram report."""

        provider = provider or FinvizAPIProvider(
            self.settings.finviz_api_token.get_secret_value()
        )
        try:
            snapshots = provider.snapshots()
        except Exception as error:
            self.store.append_json(
                "provider_health",
                {
                    "provider": provider.name,
                    "state": "unavailable",
                    "payload": {"detail": type(error).__name__},
                },
            )
            raise RuntimeError("Finviz refresh failed safely") from error

        health = provider.health()
        self.store.append_json(
            "provider_health",
            {
                "provider": health.provider,
                "state": health.state.value,
                "payload": {"detail": health.detail},
            },
        )
        report = self.run_daily(snapshots, data_mode=provider.name)
        delivery = queue_or_send(
            self.store,
            str(report["message_zh"]),
            bot_token=self.settings.telegram_bot_token,
            chat_id=self.settings.telegram_chat_id,
            kind=message_kind,
        )
        return {
            "status": "completed",
            "provider": provider.name,
            "equities_received": len(snapshots),
            "candidates_found": len(report["top_10"]),
            "telegram": delivery,
            "generated_at": report["generated_at"],
        }

    def run_daily(
        self,
        snapshots: list[SecuritySnapshot],
        *,
        data_mode: str,
        valuations: dict[str, ValuationResult] | None = None,
    ) -> dict[str, object]:
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
        operational_candidates = candidates[:MAX_OPERATIONAL_CANDIDATES]
        candidate_symbols = {candidate.symbol for candidate in operational_candidates}
        snapshots_to_persist = (
            snapshots
            if data_mode == "synthetic_replay"
            else [snapshot for snapshot in snapshots if snapshot.symbol in candidate_symbols]
        )
        for snapshot in snapshots_to_persist:
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
        for candidate in operational_candidates:
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
        regime = (
            classify_regime(0.7, 1.0, 0.4, 17.5, 58)
            if data_mode == "synthetic_replay"
            else unverified_regime()
        )
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
