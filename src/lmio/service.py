"""Application orchestration for deterministic LMIO V1 workflows."""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from lmio.candidates import transition_candidate
from lmio.config import Settings
from lmio.demo import demo_universe, meta_acceptance_input
from lmio.domain import (
    CandidateState,
    DataProvenance,
    MarketRegime,
    NewsEvent,
    ScreenCandidate,
    SecuritySnapshot,
    SignalRecord,
    ValuationResult,
)
from lmio.news import event_fingerprint
from lmio.official_news_monitor import monitor_official_news
from lmio.outcomes import TimedPrice, evaluate_timed_horizon
from lmio.pipeline import OperationalPipeline, StageResult, StageStatus
from lmio.providers.base import ProviderState
from lmio.providers.finviz_api import FinvizAPIProvider
from lmio.providers.official_rss import OfficialRSSProvider
from lmio.providers.research import OpenAINewsWorker
from lmio.providers.sec import SECProvider
from lmio.ranking import RankedCandidate, rank_top10
from lmio.reports import build_daily_report, classify_regime, unverified_regime
from lmio.research import ResearchPack, build_research_pack
from lmio.screens import run_core_screens
from lmio.sec_monitor import monitor_sec
from lmio.store import RuntimeStore
from lmio.supabase_store import SupabaseRuntimeStore
from lmio.telegram import MessageKind, queue_or_send
from lmio.top3 import evaluate_top3
from lmio.universe import UniversePolicy, build_investable_universe
from lmio.valuation import run_valuation
from lmio.valuation_inputs import FinancialEvidence, PreparedValuationInput, prepare_valuation_input

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

    def _verified_market_regime(
        self,
        provider: FinvizAPIProvider,
        snapshots: list[SecuritySnapshot],
    ) -> MarketRegime:
        """Resolve and persist one market regime, failing closed when evidence is incomplete."""

        try:
            environment = provider.market_environment(snapshots)
        except Exception as error:
            regime = unverified_regime()
            self.store.append_json(
                "provider_health",
                {
                    "provider": "market_environment",
                    "state": "unavailable",
                    "payload": {
                        "detail": type(error).__name__,
                        "required_inputs": ["SPY", "QQQ", "IWM", "VIX", "market breadth"],
                    },
                },
            )
            return regime

        classified = classify_regime(
            environment.spy_return_pct,
            environment.qqq_return_pct,
            environment.iwm_return_pct,
            environment.vix,
            environment.breadth_pct,
        )
        regime = classified.model_copy(
            update={
                "observed_at": environment.observed_at,
                "evidence": [
                    *classified.evidence,
                    f"市场广度样本 {environment.breadth_observations}",
                    f"VIX 收盘日期 {environment.vix_observed_on}",
                ],
            }
        )
        payload = {
            "environment": environment.model_dump(mode="json"),
            "regime": regime.model_dump(mode="json"),
            "calculation_version": "market-regime-v1",
        }
        self.store.append_json(
            "market_regimes",
            {
                "source": "Finviz Elite + Cboe VIX History",
                "source_url": environment.source_urls[0],
                "observed_at": environment.observed_at.isoformat(),
                "schema_version": "1",
                "payload": payload,
            },
        )
        self.store.append_json(
            "provider_health",
            {
                "provider": "market_environment",
                "state": "ready",
                "payload": {
                    "detail": f"{regime.label} at {regime.confidence:.0%} confidence",
                    "observed_at": environment.observed_at.isoformat(),
                    "sources": environment.source_urls,
                    "breadth_observations": environment.breadth_observations,
                },
            },
        )
        return regime

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
        valuation_evidence_by_symbol: (
            dict[str, FinancialEvidence | dict[str, object]] | None
        ) = None,
    ) -> dict[str, object]:
        """Run the sole production daily pipeline without any trading capability."""

        provider = finviz_provider or FinvizAPIProvider(
            self.settings.finviz_api_token.get_secret_value()
        )

        def preflight(context: dict[str, object]) -> StageResult:
            readiness = self.settings.integration_readiness()
            context["readiness"] = readiness
            if provider.health().state is ProviderState.DISABLED:
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
            if any(not item.provenance.operational for item in snapshots):
                return StageResult(
                    status=StageStatus.FAILED,
                    error_summary="NonOperationalMarketSnapshot",
                )
            context["snapshots"] = snapshots
            snapshot_ids: dict[str, str] = {}
            for snapshot in snapshots:
                snapshot_payload = snapshot.model_dump(mode="json")
                fingerprint = hashlib.sha256(
                    json.dumps(
                        {
                            "provider": provider.name,
                            "symbol": snapshot.symbol,
                            "observed_at": snapshot_payload["observed_at"],
                            "payload": snapshot_payload,
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                self.store.put_provider_snapshot(
                    fingerprint,
                    provider=provider.name,
                    symbol=snapshot.symbol,
                    company=snapshot.company,
                    observed_at=str(snapshot_payload["observed_at"]),
                    payload=snapshot_payload,
                )
                snapshot_ids[snapshot.symbol.upper()] = f"snapshot-{fingerprint}"
            context["snapshot_ids"] = snapshot_ids
            regime = self._verified_market_regime(provider, snapshots)
            context["regime"] = regime
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
                status=(
                    StageStatus.SUCCEEDED
                    if regime.label != "Unverified"
                    else StageStatus.PARTIAL
                ),
                output_count=len(snapshots),
                warning_count=int(regime.label == "Unverified"),
                evidence_references=sorted(snapshot_ids.values()),
                details={
                    "provider_snapshot_ids": snapshot_ids,
                    "market_regime": regime.label,
                    "market_regime_confidence": regime.confidence,
                },
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
            screen_run_id = self.store.append_json(
                "screen_runs",
                {
                    "calculation_version": "screens-v1",
                    "universe_run_id": None,
                    "payload": [item.model_dump(mode="json") for item in candidates],
                },
            )
            context["screen_run_id"] = f"screen-run-{screen_run_id}"
            return StageResult(
                output_count=len(candidates),
                evidence_references=[str(context["screen_run_id"])],
            )

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
            ranked = rank_top10(
                list(context.get("candidates") or []),
                run_id=str(context["run_id"]),
            )
            context["top_10_ranked"] = ranked
            context["top_10"] = [item.candidate for item in ranked]
            context["candidate_ids"] = {
                item.candidate.symbol.upper(): item.candidate_id for item in ranked
            }
            record_ids: list[str] = []
            for item in ranked:
                record_id = self.store.append_json(
                    "top10_rankings",
                    {
                        "run_id": str(context["run_id"]),
                        "symbol": item.candidate.symbol,
                        "rank": item.rank,
                        "payload": item.model_dump(mode="json"),
                    },
                )
                record_ids.append(f"top10-ranking-{record_id}")
            context["top10_ranking_ids"] = record_ids
            return StageResult(
                output_count=len(ranked),
                evidence_references=record_ids,
                details={
                    "ranked_symbols": [item.candidate.symbol for item in ranked],
                    "deduplicated": sum(bool(item.alternative_strategies) for item in ranked),
                },
            )

        def valuation_inputs(context: dict[str, object]) -> StageResult:
            ranked = list(context.get("top_10_ranked") or [])
            provided = valuation_evidence_by_symbol or {}
            snapshot_ids = dict(context.get("snapshot_ids") or {})
            prepared_by_symbol: dict[str, PreparedValuationInput] = {}
            record_ids: dict[str, str] = {}
            blocked_symbols: list[str] = []
            incomplete = 0
            for raw_item in ranked:
                item = RankedCandidate.model_validate(raw_item)
                symbol = item.candidate.symbol.upper()
                supplied = provided.get(symbol)
                if supplied is None:
                    evidence = FinancialEvidence(
                        symbol=symbol,
                        company_type="mature_non_financial",
                        provenance=item.candidate.provenance,
                        observed_at=max(
                            (entry.observed_at for entry in item.candidate.evidence),
                            default=datetime.now(UTC),
                        ),
                        source_fields={
                            "revenue": None,
                            "earnings": None,
                            "operating_cash_flow": None,
                            "capex": None,
                            "reported_free_cash_flow": None,
                            "debt": None,
                            "cash": None,
                            "net_cash": None,
                            "diluted_shares": None,
                            "market_price": item.candidate.market_price,
                        },
                        source_references={
                            "market_price": snapshot_ids.get(symbol, "missing:snapshot")
                        },
                        assumptions={},
                    )
                else:
                    evidence = (
                        supplied
                        if isinstance(supplied, FinancialEvidence)
                        else FinancialEvidence.model_validate(supplied)
                    )
                    if evidence.symbol.upper() != symbol:
                        raise ValueError("Valuation evidence symbol does not match candidate")
                    if evidence.provenance is not item.candidate.provenance:
                        raise ValueError("Valuation evidence provenance does not match candidate")
                prepared = prepare_valuation_input(evidence)
                prepared_by_symbol[symbol] = prepared
                if prepared.status != "ready":
                    blocked_symbols.append(symbol)
                    if prepared.status == "blocked":
                        incomplete += 1
                payload = {
                    "run_id": context["run_id"],
                    "candidate_id": item.candidate_id,
                    "source_snapshot_ids": [snapshot_ids.get(symbol, "missing:snapshot")],
                    "company_type": evidence.company_type,
                    "financial_evidence": evidence.model_dump(mode="json"),
                    "prepared": prepared.model_dump(mode="json"),
                    "calculation_version": prepared.model_version,
                    "recorded_at": datetime.now(UTC).isoformat(),
                }
                record_id = self.store.append_json(
                    "valuation_input_records",
                    {
                        "run_id": str(context["run_id"]),
                        "candidate_id": item.candidate_id,
                        "symbol": symbol,
                        "status": prepared.status,
                        "payload": payload,
                    },
                )
                record_ids[symbol] = f"valuation-input-{record_id}"
            context["prepared_valuation_inputs"] = prepared_by_symbol
            context["valuation_input_ids"] = record_ids
            ready_count = sum(item.status == "ready" for item in prepared_by_symbol.values())
            return StageResult(
                status=(
                    StageStatus.SUCCEEDED if ready_count == len(ranked) else StageStatus.PARTIAL
                ),
                output_count=ready_count,
                warning_count=len(ranked) - ready_count,
                error_summary=None if ready_count == len(ranked) else "Valuation inputs incomplete",
                evidence_references=sorted(record_ids.values()),
                details={
                    "inputs_attempted": len(ranked),
                    "inputs_completed": ready_count,
                    "inputs_incomplete": incomplete,
                    "blocked_symbols": blocked_symbols,
                },
            )

        def valuation_routing(context: dict[str, object]) -> StageResult:
            prepared_by_symbol = dict(context.get("prepared_valuation_inputs") or {})
            input_ids = dict(context.get("valuation_input_ids") or {})
            candidate_ids = dict(context.get("candidate_ids") or {})
            valuations: dict[str, ValuationResult] = {}
            valuation_ids: dict[str, str] = {}
            not_applicable = 0
            incomplete = 0
            failed = 0
            for symbol, raw_prepared in prepared_by_symbol.items():
                prepared = PreparedValuationInput.model_validate(raw_prepared)
                if prepared.status == "unsupported":
                    not_applicable += 1
                    continue
                if prepared.status != "ready" or prepared.valuation_input is None:
                    incomplete += 1
                    continue
                try:
                    result = run_valuation(prepared.valuation_input)
                except Exception:
                    failed += 1
                    continue
                valuations[symbol] = result
                record_id = self.store.append_json(
                    "valuation_runs",
                    {
                        "symbol": symbol,
                        "calculation_version": result.calculation_version,
                        "input_payload": {
                            "run_id": context["run_id"],
                            "candidate_id": candidate_ids[symbol],
                            "valuation_input_id": input_ids[symbol],
                            "route": prepared.route,
                            "input": prepared.valuation_input.model_dump(mode="json"),
                        },
                        "result_payload": result.model_dump(mode="json"),
                    },
                )
                valuation_ids[symbol] = f"valuation-{record_id}"
            context["valuations"] = valuations
            context["valuation_ids"] = valuation_ids
            attempted = len(prepared_by_symbol)
            valued = len(valuations)
            return StageResult(
                status=(StageStatus.SUCCEEDED if valued == attempted else StageStatus.PARTIAL),
                output_count=valued,
                warning_count=not_applicable + incomplete + failed,
                error_summary=None if valued == attempted else "Some valuations are unavailable",
                evidence_references=sorted(valuation_ids.values()),
                details={
                    "routed": attempted,
                    "valued": valued,
                    "not_applicable": not_applicable,
                    "incomplete": incomplete,
                    "failed": failed,
                },
            )

        def top3_and_report(context: dict[str, object]) -> StageResult:
            top = list(context.get("top_10") or [])
            valuations = dict(context.get("valuations") or {})
            _, preliminary = evaluate_top3(top, valuations, {})
            context["preliminary_top3_status"] = preliminary
            return StageResult(
                status=StageStatus.SUCCEEDED,
                output_count=len(preliminary.evaluations),
                evidence_references=sorted(dict(context.get("valuation_ids") or {}).values()),
                details={
                    "selection_phase": "preliminary_only",
                    "final_selection_deferred_until_research": True,
                    "reason_counts": preliminary.reason_counts,
                },
            )

        def research(context: dict[str, object]) -> StageResult:
            top = list(context.get("top_10") or [])
            valuations = dict(context.get("valuations") or {})
            valuation_ids = dict(context.get("valuation_ids") or {})
            candidate_ids = dict(context.get("candidate_ids") or {})
            news = [NewsEvent.model_validate(item) for item in self.store.news_payloads()]
            packs: dict[str, ResearchPack] = {}
            research_ids: dict[str, str] = {}
            for candidate in top:
                symbol = candidate.symbol.upper()
                pack = build_research_pack(candidate, news, valuations.get(symbol)).model_copy(
                    update={
                        "run_id": str(context["run_id"]),
                        "candidate_id": candidate_ids[symbol],
                        "valuation_id": valuation_ids.get(symbol),
                        "source_snapshot_ids": [
                            dict(context.get("snapshot_ids") or {}).get(symbol, "missing:snapshot")
                        ],
                    }
                )
                packs[symbol] = pack
                record_id = self.store.append_json(
                    "research_packs",
                    {
                        "symbol": symbol,
                        "model_version": pack.model_version,
                        "payload": pack.model_dump(mode="json"),
                    },
                )
                research_ids[symbol] = f"research-pack-{record_id}"
            selected, final_status = evaluate_top3(top, valuations, packs)
            top3_ids: list[str] = []
            for evaluation in final_status.evaluations:
                record_id = self.store.append_json(
                    "top3_evaluations",
                    {
                        "symbol": evaluation.symbol,
                        "state": evaluation.state,
                        "payload": {
                            **evaluation.model_dump(mode="json"),
                            "run_id": context["run_id"],
                            "candidate_id": candidate_ids[evaluation.symbol.upper()],
                            "valuation_id": valuation_ids.get(evaluation.symbol.upper()),
                            "research_pack_id": research_ids[evaluation.symbol.upper()],
                            "phase": "final_after_research",
                        },
                    },
                )
                top3_ids.append(f"top3-evaluation-{record_id}")
            context["research_packs"] = packs
            context["research_ids"] = research_ids
            context["top3_selected"] = selected
            context["top3_status"] = final_status
            context["top3_evaluation_ids"] = top3_ids
            snapshots = list(context.get("snapshots") or [])
            provenance = snapshots[0].provenance
            report = build_daily_report(
                top,
                universe_checked=len(snapshots),
                investable=len(list(context.get("investable") or [])),
                regime=MarketRegime.model_validate(
                    context.get("regime") or unverified_regime()
                ),
                data_mode=provider.name,
                valuations=valuations,
                research_packs=packs,
                provenance=provenance,
            )
            report_payload = report.model_dump(mode="json")
            report_id = self.store.append_json(
                "reports",
                {
                    "report_type": "daily",
                    "payload": {**report_payload, "run_id": context["run_id"]},
                },
            )
            context["report"] = report_payload
            context["report_id"] = f"report-{report_id}"
            complete = sum(pack.mandatory_completion == 1 for pack in packs.values())
            return StageResult(
                status=(
                    StageStatus.SUCCEEDED
                    if packs and complete == len(packs)
                    else StageStatus.PARTIAL
                ),
                output_count=len(packs),
                warning_count=len(packs) - complete,
                error_summary=None if complete == len(packs) else "Research evidence incomplete",
                evidence_references=[*research_ids.values(), *top3_ids],
                details={
                    "same_run_research_packages": len(packs),
                    "mandatory_complete": complete,
                    "final_top3_selected": len(selected),
                    "final_selection_after_research": True,
                },
            )

        def news_price(context: dict[str, object]) -> StageResult:
            packs = list(dict(context.get("research_packs") or {}).values())
            confirmed = sum(
                pack.news_price_confirmation.get("state") == "confirmed" for pack in packs
            )
            return StageResult(
                status=StageStatus.SUCCEEDED if confirmed == len(packs) else StageStatus.PARTIAL,
                output_count=confirmed,
                warning_count=len(packs) - confirmed,
                evidence_references=["store:research_packs:news_price_confirmation"],
            )

        def existing_output(context: dict[str, object]) -> StageResult:
            transition_ids: list[str] = []
            for candidate in list(context.get("top_10") or []):
                evidence_urls = [
                    item.source_url for item in candidate.evidence if item.source_url is not None
                ]
                transition = transition_candidate(
                    symbol=candidate.symbol,
                    strategy=candidate.strategy,
                    previous_state=CandidateState.DISCOVERED,
                    new_state=CandidateState.FILTERED,
                    reason="Current-run deterministic ranking completed.",
                    actor="screening-agent",
                    evidence_urls=evidence_urls,
                    run_id=str(context["run_id"]),
                )
                record_id = self.store.append_json(
                    "candidate_transitions",
                    {
                        "symbol": transition.symbol,
                        "strategy": transition.strategy,
                        "previous_state": transition.previous_state,
                        "new_state": transition.new_state,
                        "payload": transition.model_dump(mode="json"),
                    },
                )
                transition_ids.append(f"candidate-transition-{record_id}")
            context["candidate_transition_ids"] = transition_ids
            current_plans = [
                item
                for item in self.store.history_json("conditional_plans", 200)
                if str(dict(item.get("payload") or {}).get("run_id")) == str(context["run_id"])
            ]
            context["current_run_plans"] = current_plans
            return StageResult(
                output_count=len(transition_ids) + len(current_plans),
                evidence_references=transition_ids,
                details={
                    "candidate_transitions": len(transition_ids),
                    "same_run_conditional_plans": len(current_plans),
                },
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
                bot_token=self.settings.telegram_bot_token.get_secret_value(),
                chat_id=self.settings.telegram_chat_id.get_secret_value(),
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

        def health(context: dict[str, object]) -> StageResult:
            checks = (
                self.store.connectivity_check(),
                self.store.schema_check(),
                self.store.record_count_check(),
            )
            healthy = all(check.get("status") == "ok" for check in checks)
            lineage_payload = {
                "run_id": context["run_id"],
                "provider_snapshot_ids": dict(context.get("snapshot_ids") or {}),
                "screening_run_id": context.get("screen_run_id"),
                "candidate_ids": dict(context.get("candidate_ids") or {}),
                "top10_ranking_ids": list(context.get("top10_ranking_ids") or []),
                "valuation_input_ids": dict(context.get("valuation_input_ids") or {}),
                "valuation_ids": dict(context.get("valuation_ids") or {}),
                "research_pack_ids": dict(context.get("research_ids") or {}),
                "top3_evaluation_ids": list(context.get("top3_evaluation_ids") or []),
                "conditional_plan_ids": [
                    int(item["id"]) for item in list(context.get("current_run_plans") or [])
                ],
                "signal_ids": [],
                "outcome_ids": [],
                "report_id": context.get("report_id"),
                "provenance": sorted(
                    {item.provenance.value for item in list(context.get("top_10") or [])}
                ),
                "external_governance_integration": "planned_not_executed",
            }
            lineage_id = self.store.append_json(
                "operational_lineage",
                {
                    "run_id": str(context["run_id"]),
                    "state": "recorded",
                    "payload": lineage_payload,
                },
            )
            context["lineage_id"] = f"operational-lineage-{lineage_id}"
            return StageResult(
                status=StageStatus.SUCCEEDED if healthy else StageStatus.PARTIAL,
                output_count=len(checks),
                warning_count=0 if healthy else 1,
                evidence_references=[
                    "runtime:connectivity",
                    "runtime:schema",
                    "runtime:counts",
                    str(context["lineage_id"]),
                ],
                details={"lineage_id": context["lineage_id"]},
            )

        def signal_eligibility(context: dict[str, object]) -> StageResult:
            selected = list(context.get("top3_selected") or [])
            plans = list(context.get("current_run_plans") or [])
            approval_events = self.store.history_json("trade_plan_transitions", 200)
            ready_plans = [
                item
                for item in plans
                if str(item.get("state")) in {"plan_ready", "monitoring"}
                and any(
                    str(event.get("symbol", "")).upper() == str(item.get("symbol", "")).upper()
                    and str(event.get("new_state")) == "plan_ready"
                    and str(dict(event.get("payload") or {}).get("run_id"))
                    == str(context["run_id"])
                    and str(dict(event.get("payload") or {}).get("actor", "lmio-system"))
                    != "lmio-system"
                    for event in approval_events
                )
            ]
            eligible_symbols = {item.symbol.upper() for item in selected} & {
                str(item.get("symbol", "")).upper() for item in ready_plans
            }
            if not eligible_symbols:
                return StageResult(
                    status=StageStatus.PARTIAL,
                    warning_count=1,
                    error_summary="No selected candidate has an authenticated approved plan.",
                    evidence_references=list(context.get("top3_evaluation_ids") or []),
                    details={
                        "eligible": 0,
                        "signals_created": 0,
                        "operator_action_required": True,
                    },
                )
            return StageResult(
                status=StageStatus.SUCCEEDED,
                output_count=len(eligible_symbols),
                evidence_references=list(context.get("top3_evaluation_ids") or []),
                details={
                    "eligible": len(eligible_symbols),
                    "signals_created": 0,
                    "operator_action_required": True,
                },
            )

        def due_outcomes(_: dict[str, object]) -> StageResult:
            result = self.process_due_outcomes()
            return StageResult(
                status=(StageStatus.SUCCEEDED if result["failed"] == 0 else StageStatus.PARTIAL),
                output_count=int(result["completed"]),
                warning_count=int(result["unavailable"]),
                error_summary=(
                    None if result["failed"] == 0 else "One or more due outcomes failed."
                ),
                evidence_references=["store:signal_outcomes"],
            )

        def performance(_: dict[str, object]) -> StageResult:
            result = self.aggregate_strategy_performance()
            return StageResult(
                status=(
                    StageStatus.SUCCEEDED if result["eligible_outcomes"] else StageStatus.SKIPPED
                ),
                output_count=int(result["summaries"]),
                evidence_references=["store:strategy_performance"],
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
            18: signal_eligibility,
            19: due_outcomes,
            20: performance,
            21: health,
        }
        return OperationalPipeline(self.store, handlers).run(
            initial_context={
                "valuation_evidence_by_symbol": valuation_evidence_by_symbol or {},
            }
        )

    def create_signal_from_approved_plan(self, plan_id: int, *, actor: str) -> dict[str, object]:
        """Create research signal evidence after authenticated plan approval.

        This is a decision-support record only. It has no broker, order or
        execution side effect.
        """

        plan_row = next(
            (
                item
                for item in self.store.history_json("conditional_plans", 200)
                if int(item["id"]) == plan_id
            ),
            None,
        )
        if plan_row is None:
            raise ValueError("Conditional plan does not exist")
        plan_payload = dict(plan_row.get("payload") or {})
        if str(plan_row.get("state")) not in {"plan_ready", "monitoring"}:
            raise ValueError("Conditional plan has not been approved")
        run_id = str(plan_payload.get("run_id", ""))
        symbol = str(plan_row.get("symbol", "")).upper()
        if not run_id or not symbol:
            raise ValueError("Plan lineage is incomplete")
        approval = next(
            (
                item
                for item in self.store.history_json("trade_plan_transitions", 200)
                if str(item.get("symbol", "")).upper() == symbol
                and str(item.get("new_state")) == "plan_ready"
                and str(dict(item.get("payload") or {}).get("run_id")) == run_id
                and str(dict(item.get("payload") or {}).get("actor")) == actor
            ),
            None,
        )
        if approval is None:
            raise ValueError("Plan approval must be attributable to this authenticated operator")
        expires_at = datetime.fromisoformat(str(plan_payload["expires_at"]).replace("Z", "+00:00"))
        if expires_at <= datetime.now(UTC):
            raise ValueError("Conditional plan has expired")

        evaluation = next(
            (
                item
                for item in self.store.history_json("top3_evaluations", 200)
                if str(item.get("symbol", "")).upper() == symbol
                and str(dict(item.get("payload") or {}).get("run_id")) == run_id
                and str(item.get("state")) == "top3_selected"
            ),
            None,
        )
        ranking = next(
            (
                item
                for item in self.store.history_json("top10_rankings", 200)
                if str(item.get("symbol", "")).upper() == symbol
                and str(item.get("run_id")) == run_id
            ),
            None,
        )
        if evaluation is None or ranking is None:
            raise ValueError("Selected candidate lineage is unavailable")
        ranked = RankedCandidate.model_validate(ranking["payload"])

        snapshots = self.store.history_json("provider_snapshots", 200)
        symbol_snapshot = next(
            (item for item in snapshots if str(item.get("symbol", "")).upper() == symbol), None
        )
        benchmark_snapshot = next(
            (item for item in snapshots if str(item.get("symbol", "")).upper() == "SPY"), None
        )
        if symbol_snapshot is None or benchmark_snapshot is None:
            raise ValueError("Current symbol and SPY snapshots are required")
        observed_at = datetime.fromisoformat(
            str(symbol_snapshot["observed_at"]).replace("Z", "+00:00")
        )
        benchmark_observed_at = datetime.fromisoformat(
            str(benchmark_snapshot["observed_at"]).replace("Z", "+00:00")
        )
        current = datetime.now(UTC)
        symbol_stale = current - observed_at > timedelta(hours=24)
        benchmark_stale = current - benchmark_observed_at > timedelta(hours=24)
        if symbol_stale or benchmark_stale:
            raise ValueError("Current market evidence is stale")
        symbol_payload = dict(symbol_snapshot.get("payload") or {})
        benchmark_payload = dict(benchmark_snapshot.get("payload") or {})
        signal_price = symbol_payload.get("price")
        benchmark_price = benchmark_payload.get("price")
        if signal_price is None or benchmark_price is None:
            raise ValueError("Current market prices are unavailable")

        signal_id = (
            "signal-"
            + hashlib.sha256(
                f"{run_id}:{plan_id}:{symbol}:{observed_at.isoformat()}".encode()
            ).hexdigest()[:20]
        )
        signal = SignalRecord(
            signal_id=signal_id,
            run_id=run_id,
            candidate_id=ranked.candidate_id,
            symbol=symbol,
            strategy=ranked.candidate.strategy,
            created_at=current,
            signal_price=float(signal_price),
            benchmark="SPY",
            benchmark_price=float(benchmark_price),
            source_snapshot_ids=[
                f"provider-snapshot-{symbol_snapshot['id']}",
                f"provider-snapshot-{benchmark_snapshot['id']}",
            ],
            scores=ranked.candidate.scores,
            candidate_state=ranked.candidate.state,
            plan_id=str(plan_id),
            approved_by=actor,
            invalidation_conditions=[str(plan_payload["invalidation_condition"])],
            provenance=ranked.candidate.provenance,
            model_versions={
                "scores": ranked.candidate.scores.calculation_version,
                "signal": "signal-evidence-v1",
            },
        )
        record_id = self.store.append_json(
            "signals",
            {
                "symbol": symbol,
                "strategy": signal.strategy,
                "state": "active_research_signal",
                "payload": signal.model_dump(mode="json"),
            },
        )
        return {
            "id": record_id,
            "signal_id": signal_id,
            "run_id": run_id,
            "status": "created",
            "execution_capability": False,
        }

    @staticmethod
    def _outcome_due_times(signal_time: datetime) -> dict[str, datetime]:
        new_york = ZoneInfo("America/New_York")
        local_signal = signal_time.astimezone(new_york)

        def next_close(trading_days: int) -> datetime:
            day = local_signal.date()
            remaining = trading_days
            while remaining > 0:
                day += timedelta(days=1)
                if day.weekday() < 5:
                    remaining -= 1
            return datetime(day.year, day.month, day.day, 16, tzinfo=new_york).astimezone(UTC)

        same_day_close = datetime(
            local_signal.year,
            local_signal.month,
            local_signal.day,
            16,
            tzinfo=new_york,
        )
        if local_signal.weekday() >= 5 or same_day_close <= signal_time:
            close_due = next_close(1)
        else:
            close_due = same_day_close.astimezone(UTC)
        return {
            "1h": signal_time + timedelta(hours=1),
            "close": close_due,
            "1d": next_close(1),
            "5d": next_close(5),
            "20d": next_close(20),
        }

    def process_due_outcomes(self, *, now: datetime | None = None) -> dict[str, int | str]:
        """Progress due signal horizons using only persisted timestamped prices."""

        current = now or datetime.now(UTC)
        signals = self.store.history_json("signals", 200)
        existing = self.store.history_json("signal_outcomes", 200)
        latest_status: dict[tuple[str, str], str] = {}
        for item in existing:
            key = (
                str(dict(item.get("payload") or {}).get("signal_id")),
                str(item["horizon"]),
            )
            latest_status.setdefault(key, str(dict(item.get("payload") or {}).get("status")))
        snapshot_rows = self.store.history_json("provider_snapshots", 200)
        parsed_snapshots: list[tuple[dict[str, object], dict[str, object], datetime]] = []
        for row in snapshot_rows:
            payload = dict(row.get("payload") or {})
            observed_at = datetime.fromisoformat(
                str(row.get("observed_at") or payload.get("observed_at")).replace("Z", "+00:00")
            )
            parsed_snapshots.append((row, payload, observed_at))
        benchmark_rows = [
            item
            for item in parsed_snapshots
            if str(item[0].get("symbol", "")).upper() == "SPY" and item[1].get("price") is not None
        ]
        by_symbol: dict[str, list[TimedPrice]] = {}
        for row, payload, observed_at in parsed_snapshots:
            price = payload.get("price")
            if price is not None:
                benchmark = min(
                    benchmark_rows,
                    key=lambda item: abs((item[2] - observed_at).total_seconds()),
                    default=None,
                )
                benchmark_price = (
                    float(benchmark[1]["price"])
                    if benchmark is not None
                    and abs((benchmark[2] - observed_at).total_seconds()) <= 15 * 60
                    else None
                )
                references = [f"provider-snapshot-{row['id']}"]
                if benchmark_price is not None and benchmark is not None:
                    references.append(f"provider-snapshot-{benchmark[0]['id']}")
                by_symbol.setdefault(str(row.get("symbol", "")).upper(), []).append(
                    TimedPrice(
                        observed_at=observed_at,
                        price=float(price),
                        benchmark_price=benchmark_price,
                        evidence_reference="|".join(references),
                    )
                )
        counts = {
            "completed": 0,
            "not_due": 0,
            "unavailable": 0,
            "failed": 0,
            "unchanged": 0,
        }
        for row in signals:
            try:
                signal = SignalRecord.model_validate(row["payload"])
            except Exception:
                counts["failed"] += 1
                continue
            due_times = self._outcome_due_times(signal.created_at)
            for horizon, due_at in due_times.items():
                key = (signal.signal_id, horizon)
                if latest_status.get(key) == "completed":
                    counts["unchanged"] += 1
                    continue
                outcome = evaluate_timed_horizon(
                    horizon=horizon,
                    signal_time=signal.created_at,
                    signal_price=signal.signal_price,
                    benchmark_price=signal.benchmark_price,
                    due_at=due_at,
                    prices=by_symbol.get(signal.symbol, []),
                    now=current,
                )
                counts[outcome.status.value] += 1
                if latest_status.get(key) == outcome.status.value:
                    counts["unchanged"] += 1
                    continue
                outcome_id = (
                    "outcome-"
                    + hashlib.sha256(f"{signal.signal_id}:{horizon}".encode()).hexdigest()[:20]
                )
                self.store.append_json(
                    "signal_outcomes",
                    {
                        "symbol": signal.symbol,
                        "strategy": signal.strategy,
                        "signal_date": signal.created_at.date().isoformat(),
                        "horizon": horizon,
                        "return_pct": outcome.return_pct,
                        "max_adverse_excursion_pct": outcome.max_adverse_excursion_pct,
                        "max_favourable_excursion_pct": outcome.max_favourable_excursion_pct,
                        "payload": {
                            **asdict(outcome),
                            "status": outcome.status,
                            "outcome_id": outcome_id,
                            "signal_id": signal.signal_id,
                            "run_id": signal.run_id,
                            "due_at": due_at.isoformat(),
                            "actual_observation_time": (
                                outcome.actual_observation_time.isoformat()
                                if outcome.actual_observation_time
                                else None
                            ),
                            "evaluated_at": current.isoformat(),
                            "signal_price": signal.signal_price,
                            "benchmark_signal_price": signal.benchmark_price,
                            "horizon_price": (
                                round(signal.signal_price * (1 + outcome.return_pct), 6)
                                if outcome.return_pct is not None
                                else None
                            ),
                            "benchmark_horizon_price": (
                                round(
                                    signal.benchmark_price * (1 + outcome.benchmark_return_pct),
                                    6,
                                )
                                if outcome.benchmark_return_pct is not None
                                else None
                            ),
                            "invalidation_status": (
                                "triggered"
                                if outcome.invalidation_triggered is True
                                else "not_triggered"
                                if outcome.invalidation_triggered is False
                                else "not_evaluated"
                            ),
                            "evidence_references": list(outcome.evidence_references),
                        },
                    },
                )
        return {"status": "completed", **counts}

    def aggregate_strategy_performance(self) -> dict[str, int | str]:
        """Aggregate only completed outcomes; unknown values never become zero."""

        completed = [
            item
            for item in self.store.history_json("signal_outcomes", 200)
            if dict(item.get("payload") or {}).get("status") == "completed"
            and item.get("return_pct") is not None
        ]
        groups: dict[tuple[str, str], list[dict[str, object]]] = {}
        for item in completed:
            groups.setdefault((str(item["strategy"]), str(item["horizon"])), []).append(item)
        for (strategy, horizon), items in groups.items():
            returns = [float(item["return_pct"]) for item in items]
            self.store.append_json(
                "strategy_performance",
                {
                    "strategy": strategy,
                    "horizon": horizon,
                    "regime": None,
                    "payload": {
                        "sample_count": len(items),
                        "hit_rate": sum(value > 0 for value in returns) / len(returns),
                        "average_return": sum(returns) / len(returns),
                        "model_version": "strategy-performance-v2",
                        "eligibility": "completed_outcomes_only",
                    },
                },
            )
        return {
            "status": "completed",
            "eligible_outcomes": len(completed),
            "summaries": len(groups),
        }

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

        regime = self._verified_market_regime(provider, snapshots)
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
        report = self.run_daily(snapshots, data_mode=provider.name, regime=regime)
        if report.get("provenance") != DataProvenance.LIVE_AUTHORISED:
            raise RuntimeError("Only live authorised reports may be delivered to Telegram")
        delivery = queue_or_send(
            self.store,
            str(report["message_zh"]),
            bot_token=self.settings.telegram_bot_token.get_secret_value(),
            chat_id=self.settings.telegram_chat_id.get_secret_value(),
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
            result["ai_summaries"] = self.summarise_latest_news()
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
        result["ai_summaries"] = self.summarise_latest_news()
        return result

    def summarise_latest_news(self, limit: int = 12) -> dict[str, object]:
        """Add bounded AI summaries to unsummarised official events, failing closed."""

        api_key = self.settings.openai_api_key.get_secret_value().strip()
        if not api_key:
            return {"status": "disabled", "summarised": 0, "detail": "API key not configured"}

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        used = self.store.ai_usage_total(month_start.isoformat(), next_month.isoformat())
        cap = self.settings.openai_monthly_cap_usd
        reserve = (
            2_000 * self.settings.openai_input_usd_per_million
            + 500 * self.settings.openai_output_usd_per_million
        ) / 1_000_000
        if used + reserve > cap:
            return {"status": "cap_reached", "summarised": 0, "spent_usd": round(used, 6)}

        worker = OpenAINewsWorker(
            api_key=api_key,
            model=self.settings.openai_model,
        )
        summarised = 0
        failed = 0
        for stored in self.latest_news(limit=max(1, min(limit, 25))):
            if isinstance(stored.get("ai_summary"), dict):
                continue
            if used + reserve > cap:
                break
            event = NewsEvent.model_validate(stored)
            minimal = {
                "headline": event.headline,
                "event_type": event.event_type,
                "source": event.source,
                "published_at": event.published_at.isoformat(),
                "symbols": event.symbols,
                "significance": event.significance,
            }
            try:
                result = worker.analyse(minimal)
            except Exception as error:
                failed += 1
                self.store.append_json(
                    "provider_health",
                    {
                        "provider": worker.name,
                        "state": "unavailable",
                        "payload": {"detail": type(error).__name__, "failed_safely": True},
                    },
                )
                continue
            usage = result.pop("usage")
            cost = (
                usage["input_tokens"] * self.settings.openai_input_usd_per_million
                + usage["output_tokens"] * self.settings.openai_output_usd_per_million
            ) / 1_000_000
            used += cost
            self.store.append_json(
                "ai_usage",
                {
                    "model": self.settings.openai_model,
                    "cost_usd": cost,
                    "payload": {
                        "cost_usd": cost,
                        "input_tokens": usage["input_tokens"],
                        "output_tokens": usage["output_tokens"],
                        "purpose": "official_news_summary",
                    },
                },
            )
            updated = {**stored, "ai_summary": result}
            self.store.update_news_event(event_fingerprint(event), updated)
            summarised += 1

        return {
            "status": "ready" if not failed else "partial",
            "summarised": summarised,
            "failed": failed,
            "spent_usd": round(used, 6),
            "monthly_cap_usd": cap,
        }

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
        run_id: str = "standalone-daily-run",
        regime: MarketRegime | None = None,
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
        resolved_regime = (
            regime
            if regime is not None
            else (
                classify_regime(0.7, 1.0, 0.4, 17.5, 58)
                if provenance is DataProvenance.SYNTHETIC_REPLAY
                else unverified_regime()
            )
        )
        report = build_daily_report(
            candidates,
            universe_checked=len(snapshots),
            investable=len(investable),
            regime=resolved_regime,
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
                    run_id=run_id,
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
                        run_id=run_id,
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
