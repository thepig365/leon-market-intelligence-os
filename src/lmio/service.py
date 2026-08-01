"""Application orchestration for deterministic LMIO V1 workflows."""

import hashlib
import json

from lmio.candidates import transition_candidate
from lmio.config import Settings
from lmio.demo import demo_universe, meta_acceptance_input
from lmio.domain import (
    CandidateState,
    DataProvenance,
    NewsEvent,
    ScreenCandidate,
    SecuritySnapshot,
    ValuationResult,
)
from lmio.official_news_monitor import monitor_official_news
from lmio.providers.finviz_api import FinvizAPIProvider
from lmio.providers.official_rss import OfficialRSSProvider
from lmio.providers.sec import SECProvider
from lmio.reports import build_daily_report, classify_regime, unverified_regime
from lmio.research import build_research_pack
from lmio.screens import run_core_screens
from lmio.sec_monitor import monitor_sec
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
        valuation = run_valuation(meta_acceptance_input())
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

        provider = provider or FinvizAPIProvider(self.settings.finviz_api_token.get_secret_value())
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
        if report.get("provenance") != DataProvenance.LIVE_AUTHORISED:
            raise RuntimeError("Only live authorised reports may be delivered to Telegram")
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

    def finviz_symbol_snapshot(
        self,
        symbol: str,
        *,
        provider: FinvizAPIProvider | None = None,
    ) -> SecuritySnapshot | None:
        """Fetch one current Finviz snapshot without running the full universe screen."""

        provider = provider or FinvizAPIProvider(self.settings.finviz_api_token.get_secret_value())
        try:
            snapshots = provider.snapshots(symbols=[symbol])
        except Exception as error:
            self.store.append_json(
                "provider_health",
                {
                    "provider": provider.name,
                    "state": "unavailable",
                    "payload": {"detail": type(error).__name__},
                },
            )
            raise RuntimeError("Finviz symbol lookup failed safely") from error

        health = provider.health()
        self.store.append_json(
            "provider_health",
            {
                "provider": health.provider,
                "state": health.state.value,
                "payload": {"detail": health.detail},
            },
        )
        return next(
            (snapshot for snapshot in snapshots if snapshot.symbol == symbol.upper()),
            None,
        )

    def refresh_official_news(
        self,
        *,
        macro_provider: OfficialRSSProvider | None = None,
        sec_provider: SECProvider | None = None,
    ) -> dict[str, object]:
        """Refresh free official macro releases and SEC events without trading."""

        macro_provider = macro_provider or OfficialRSSProvider()
        sec_provider = sec_provider or SECProvider(self.settings.sec_user_agent)
        result: dict[str, object] = {}

        try:
            macro = monitor_official_news(macro_provider, self.store)
        except RuntimeError as error:
            macro = {"status": "unavailable", "detail": type(error).__name__}
            macro_state = "unavailable"
        else:
            macro_state = "degraded" if macro["failed_feeds"] else "ready"
        self.store.append_json(
            "provider_health",
            {
                "provider": macro_provider.name,
                "state": macro_state,
                "payload": {
                    "detail": "official macro release refresh",
                    "failed_feeds": macro.get("failed_feeds", 0),
                },
            },
        )
        result["macro"] = macro

        if not self.settings.sec_user_agent.strip():
            result["sec"] = {"status": "disabled", "detail": "SEC_USER_AGENT is not configured"}
            return result

        configured = self.settings.parsed_sec_watchlist()
        report = self.store.latest_json("reports") or {}
        candidate_symbols = {
            str(item.get("symbol", "")).strip().upper()
            for item in list(report.get("top_10") or [])[:10]
            if isinstance(item, dict) and str(item.get("symbol", "")).strip()
        }
        unresolved = candidate_symbols - configured.keys()
        resolution_failed = False
        if unresolved:
            try:
                configured.update(sec_provider.ticker_ciks(unresolved))
            except Exception:
                resolution_failed = True
        try:
            sec = monitor_sec(sec_provider, self.store, configured)
        except Exception as error:
            sec = {"status": "unavailable", "detail": type(error).__name__}
            sec_state = "unavailable"
        else:
            sec_state = "degraded" if resolution_failed else "ready"
            sec["unresolved_symbols"] = len(candidate_symbols - configured.keys())
        self.store.append_json(
            "provider_health",
            {
                "provider": sec_provider.name,
                "state": sec_state,
                "payload": {
                    "detail": "official SEC watchlist refresh",
                    "watchlist_symbols": len(configured),
                    "resolution_failed": resolution_failed,
                },
            },
        )
        result["sec"] = sec
        return result

    def latest_news(self, limit: int = 100) -> list[dict[str, object]]:
        """Return news by actual publication time, not ingestion order."""

        bounded_limit = max(1, min(limit, 500))
        events = self.store.news_payloads(limit=min(bounded_limit * 4, 2000))
        return sorted(
            events,
            key=lambda event: (
                str(event.get("published_at", "")),
                int(event.get("significance", 0)),
            ),
            reverse=True,
        )[:bounded_limit]

    def run_daily(
        self,
        snapshots: list[SecuritySnapshot],
        *,
        data_mode: str,
        valuations: dict[str, ValuationResult] | None = None,
    ) -> dict[str, object]:
        if not snapshots:
            raise ValueError("A daily run requires at least one snapshot")
        provenances = {snapshot.provenance for snapshot in snapshots}
        if len(provenances) != 1:
            raise ValueError("A daily run cannot mix provenance classes")
        provenance = provenances.pop()
        for valuation in (valuations or {}).values():
            if valuation.provenance is not provenance:
                raise ValueError("Valuation provenance must match snapshot provenance")

        policy = UniversePolicy()
        investable = build_investable_universe(snapshots, policy)
        serialised = [item.model_dump(mode="json") for item in investable]
        input_hash = hashlib.sha256(json.dumps(serialised, sort_keys=True).encode()).hexdigest()
        candidates = run_core_screens(investable)
        operational_candidates = candidates[:MAX_OPERATIONAL_CANDIDATES]
        regime = (
            classify_regime(0.7, 1.0, 0.4, 17.5, 58)
            if provenance is DataProvenance.SYNTHETIC_REPLAY
            else unverified_regime()
        )
        report = build_daily_report(
            candidates,
            universe_checked=len(snapshots),
            investable=len(investable),
            regime=regime,
            data_mode=data_mode,
            valuations=valuations,
            provenance=provenance,
        )
        report_payload = report.model_dump(mode="json")
        if not provenance.operational:
            self.store.append_json(
                "synthetic_records",
                {
                    "record_type": "daily_run",
                    "provenance": provenance,
                    "payload": {
                        "input_hash": input_hash,
                        "snapshots": serialised,
                        "report": report_payload,
                    },
                },
            )
            return report_payload

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
        candidate_symbols = {candidate.symbol for candidate in operational_candidates}
        for snapshot in [item for item in snapshots if item.symbol in candidate_symbols]:
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
        self.store.append_json(
            "reports",
            {"report_type": "daily", "payload": report_payload},
        )
        return report_payload

    def run_meta_acceptance(self) -> dict[str, object]:
        data = meta_acceptance_input()
        result = run_valuation(data)
        self.store.append_json(
            "synthetic_records",
            {
                "record_type": "valuation_acceptance",
                "provenance": data.provenance,
                "payload": {
                    "input": data.model_dump(mode="json"),
                    "result": result.model_dump(mode="json"),
                },
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
