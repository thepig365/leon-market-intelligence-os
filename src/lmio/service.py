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
from lmio.pipeline import OperationalPipeline, StageResult, StageStatus
from lmio.providers.finviz_api import FinvizAPIProvider
from lmio.providers.official_rss import OfficialRSSProvider
from lmio.providers.sec import SECProvider
from lmio.reports import build_daily_report, classify_regime, unverified_regime
from lmio.research import ResearchPack, build_research_pack
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

    def run_operational_pipeline(
        self,
        *,
        finviz_provider: FinvizAPIProvider | None = None,
    ) -> dict[str, object]:
        """Run the sole production daily pipeline without any trading capability."""

        provider = finviz_provider or FinvizAPIProvider(
            self.settings.finviz_api_token.get_secret_value()
        )

        def preflight(context: dict[str, object]) -> StageResult:
            readiness = self.settings.integration_readiness()
            context["readiness"] = readiness
            if not provider.health().configured:
                return StageResult(
                    status=StageStatus.FAILED,
                    error_summary="FinvizNotConfigured",
                    evidence_references=["settings:integration_readiness:finviz"],
                )
            return StageResult(
                output_count=1,
                evidence_references=["settings:safety:CAN_TRADE=false"],
            )

        def market_snapshot(context: dict[str, object]) -> StageResult:
            snapshots = provider.snapshots()
            if not snapshots:
                return StageResult(
                    status=StageStatus.FAILED,
                    error_summary="EmptyMarketSnapshot",
                )
            context["snapshots"] = snapshots
            evidence = provider.last_ingestion_evidence or {}
            self.store.append_json(
                "provider_health",
                {
                    "provider": provider.name,
                    "state": provider.health().state,
                    "payload": {"detail": provider.health().detail, "ingestion": evidence},
                },
            )
            return StageResult(
                output_count=len(snapshots),
                evidence_references=[str(evidence.get("snapshot_id", "finviz:no-snapshot-id"))],
            )

        def official_refresh(context: dict[str, object]) -> StageResult:
            result = self.refresh_official_news()
            context["official_refresh"] = result
            macro = dict(result.get("macro") or {})
            status = StageStatus.SUCCEEDED
            if macro.get("status") in {"unavailable", "partial"}:
                status = StageStatus.PARTIAL
            return StageResult(
                status=status,
                output_count=int(macro.get("stored", 0)),
                warning_count=int(macro.get("failed_feeds", 0)),
                evidence_references=["store:provider_health:official_macro"],
            )

        def sec_refresh(context: dict[str, object]) -> StageResult:
            result = dict(dict(context.get("official_refresh") or {}).get("sec") or {})
            state = str(result.get("status", "disabled"))
            if state == "failed":
                status = StageStatus.FAILED
            elif state in {"partial", "unavailable"}:
                status = StageStatus.PARTIAL
            elif state == "disabled":
                status = StageStatus.SKIPPED
            else:
                status = StageStatus.SUCCEEDED
            return StageResult(
                status=status,
                output_count=int(result.get("stored", result.get("succeeded", 0))),
                warning_count=int(result.get("failed", 0)),
                error_summary=None if state not in {"failed", "unavailable"} else state,
                evidence_references=["store:provider_health:sec_edgar"],
            )

        def universe(context: dict[str, object]) -> StageResult:
            snapshots = list(context.get("snapshots") or [])
            investable = build_investable_universe(snapshots, UniversePolicy())
            context["investable"] = investable
            return StageResult(output_count=len(investable))

        def screens(context: dict[str, object]) -> StageResult:
            candidates = run_core_screens(list(context.get("investable") or []))
            context["candidates"] = candidates
            return StageResult(output_count=len(candidates))

        def pattern(context: dict[str, object]) -> StageResult:
            candidates = list(context.get("candidates") or [])
            return StageResult(output_count=sum(item.pattern is not None for item in candidates))

        def scoring(context: dict[str, object]) -> StageResult:
            candidates = list(context.get("candidates") or [])
            return StageResult(
                output_count=len(candidates),
                evidence_references=["calculation:screens-v1:four-dimension-scores"],
            )

        def top10(context: dict[str, object]) -> StageResult:
            top = list(context.get("candidates") or [])[:10]
            context["top_10"] = top
            return StageResult(output_count=len(top))

        def valuation_inputs(context: dict[str, object]) -> StageResult:
            top = list(context.get("top_10") or [])
            ready = [item for item in top if not item.missing_fields]
            context["valuation_ready"] = ready
            return StageResult(
                status=StageStatus.SUCCEEDED if len(ready) == len(top) else StageStatus.PARTIAL,
                output_count=len(ready),
                warning_count=len(top) - len(ready),
                error_summary=(
                    None if len(ready) == len(top) else "Missing provider-neutral valuation inputs"
                ),
            )

        def valuation_routing(context: dict[str, object]) -> StageResult:
            ready = list(context.get("valuation_ready") or [])
            incomplete = bool(context.get("top_10")) and not ready
            return StageResult(
                status=StageStatus.PARTIAL if incomplete else StageStatus.SUCCEEDED,
                output_count=len(ready),
                warning_count=1 if incomplete else 0,
                evidence_references=["valuation:provider-neutral-routing"],
            )

        def top3_and_report(context: dict[str, object]) -> StageResult:
            snapshots = list(context.get("snapshots") or [])
            report = self.run_daily(snapshots, data_mode=provider.name)
            context["report"] = report
            top3 = dict(report.get("top_3_status") or {})
            available = bool(top3.get("available"))
            return StageResult(
                status=StageStatus.SUCCEEDED if available else StageStatus.PARTIAL,
                output_count=len(top3.get("evaluations") or []),
                warning_count=0 if available else 1,
                error_summary=None if available else str(top3.get("message", "Top 3 unavailable")),
                evidence_references=["store:top3_evaluations", "store:reports:daily"],
            )

        def research(context: dict[str, object]) -> StageResult:
            packs = self.research_latest(limit=10)
            context["research_packs"] = packs
            return StageResult(
                status=StageStatus.SUCCEEDED if packs else StageStatus.PARTIAL,
                output_count=len(packs),
                warning_count=0 if packs else 1,
                evidence_references=["store:research_packs"],
            )

        def news_price(context: dict[str, object]) -> StageResult:
            packs = list(context.get("research_packs") or [])
            confirmed = sum(bool(pack.get("news_price_confirmation")) for pack in packs)
            return StageResult(
                status=StageStatus.SUCCEEDED if confirmed == len(packs) else StageStatus.PARTIAL,
                output_count=confirmed,
                warning_count=len(packs) - confirmed,
                evidence_references=["store:research_packs:news_price_confirmation"],
            )

        def existing_output(context: dict[str, object]) -> StageResult:
            return StageResult(
                output_count=len(list(context.get("top_10") or [])),
                evidence_references=["store:candidate_transitions", "store:conditional_plans"],
            )

        def daily_brief(context: dict[str, object]) -> StageResult:
            report = dict(context.get("report") or {})
            if not report.get("message_zh"):
                return StageResult(status=StageStatus.FAILED, error_summary="MissingChineseBrief")
            return StageResult(output_count=1, evidence_references=["store:reports:daily"])

        def telegram(context: dict[str, object]) -> StageResult:
            report = dict(context.get("report") or {})
            delivery = queue_or_send(
                self.store,
                str(report["message_zh"]),
                bot_token=self.settings.telegram_bot_token,
                chat_id=self.settings.telegram_chat_id,
                kind=MessageKind.PREMARKET,
            )
            context["telegram"] = delivery
            return StageResult(
                status=(
                    StageStatus.SUCCEEDED
                    if delivery in {"sent", "deduplicated"}
                    else StageStatus.PARTIAL
                ),
                output_count=1,
                warning_count=0 if delivery in {"sent", "deduplicated"} else 1,
                evidence_references=["store:telegram_deliveries"],
            )

        def health(_: dict[str, object]) -> StageResult:
            checks = (
                self.store.connectivity_check(),
                self.store.schema_check(),
                self.store.record_count_check(),
            )
            healthy = all(check.get("status") == "ok" for check in checks)
            return StageResult(
                status=StageStatus.SUCCEEDED if healthy else StageStatus.PARTIAL,
                output_count=len(checks),
                warning_count=0 if healthy else 1,
                evidence_references=["runtime:connectivity", "runtime:schema", "runtime:counts"],
            )

        handlers = {
            1: preflight,
            2: market_snapshot,
            3: official_refresh,
            4: sec_refresh,
            5: universe,
            6: screens,
            7: pattern,
            8: scoring,
            9: top10,
            10: valuation_inputs,
            11: valuation_routing,
            12: top3_and_report,
            13: research,
            14: news_price,
            15: existing_output,
            16: daily_brief,
            17: telegram,
            21: health,
        }
        return OperationalPipeline(self.store, handlers).run()

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
        ingestion_evidence = provider.last_ingestion_evidence or {}
        self.store.append_json(
            "provider_health",
            {
                "provider": health.provider,
                "state": health.state.value,
                "payload": {"detail": health.detail, "ingestion": ingestion_evidence},
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
            if sec.get("status") == "failed":
                sec_state = "unavailable"
            elif sec.get("status") == "partial" or resolution_failed:
                sec_state = "degraded"
            else:
                sec_state = "ready"
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
        research_packs: dict[str, ResearchPack] | None = None,
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
            research_packs=research_packs,
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
        for evaluation in report.top_3_status.evaluations:
            self.store.append_json(
                "top3_evaluations",
                {
                    "symbol": evaluation.symbol,
                    "state": evaluation.state,
                    "payload": evaluation.model_dump(mode="json"),
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
