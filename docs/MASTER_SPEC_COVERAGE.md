# LMIO Master Spec Coverage

> Coverage means code and deterministic evidence unless a row names a redacted
> live run. See `OPERATIONAL_ACCEPTANCE_REPORT.md` for the six-level verdict.

This matrix is the implementation map for the governing
`LEON_MARKET_INTELLIGENCE_OS_MASTER_SPEC.md`. “Implemented” means the capability
has deterministic code and local automated evidence. It does not imply that an
external provider or protected production environment has been activated.

## Product boundary

| Requirement | Status | Evidence |
| --- | --- | --- |
| US equities, Chinese-first decision support | Implemented | `config.py`, `reports.py`, dashboard |
| No live or paper trading | Implemented and startup-enforced | `config.py`, `security.py`, security tests |
| Bayview OS is canonical project memory | Implemented | architecture and Bayview OS project record |
| Runtime evidence remains in LMIO | Implemented | versioned SQLite migrations |

## Research pipeline

| Requirement | Status | Evidence |
| --- | --- | --- |
| Investability and liquidity universe | Implemented | `universe.py`, tests |
| Authorised current-data ingestion | Manual CSV and official Finviz Elite API adapters implemented with freshness, timezone, duplicate, size, row-count, retry and completeness gates; live API verification still pending | `providers/csv_snapshot.py`, `providers/finviz_api.py`, `docs/AUTHORISED_DATA_IMPORT.md`, tests |
| Independent V1 strategy screens | Implemented | `screens.py` |
| Quality growth, revisions, institutional, activist, insider, QARP, PEAD, news, oversold, short squeeze | Implemented | deterministic combination rules and tests |
| Four dimension scoring | Implemented | `scoring.py` |
| Earnings revision breadth and EPS revision | Implemented | `screens.py`, tests |
| Official SEC monitoring | Implemented with configured and latest-Top-10 watchlist coverage; protected refresh verification pending | `providers/sec.py`, `sec_monitor.py`, `service.py` |
| 13F, Schedule 13D/13G and Form 4 parsing | Implemented with bounded official-document fetch and ingestion dedupe | `sec_ownership.py`, migration 004, parser/monitor tests |
| News normalisation, dedupe and impact | Implemented, including allowlisted Federal Reserve and BLS official feeds | `providers/official_rss.py`, `official_news_monitor.py`, `news.py`, `news_plan.py` |
| Directional reaction windows, VWAP, opening range and gap retention | Implemented | `news_plan.py`, API and news-plan tests |
| Three valuation perspectives and sensitivity | Implemented for supported company types; multi-model output combines applicable DCF and approved market-multiple inputs | `valuation.py`, `routing.py` |
| Banks, REITs, unprofitable and cyclical routing | Safely blocked from generic DCF | `routing.py`, tests |
| Deterministic Top 10 ranking | Implemented with symbol dedupe, stable tie-breaks, confidence/completeness/freshness penalties and persisted reasons | `ranking.py`, `tests/test_ranking.py` |
| Top 3 decision cards | Implemented as preliminary eligibility followed by same-run final selection after valuation and research | `top3.py`, `service.py`, operational-pipeline tests |
| 15-field research package | Implemented and bound to the current run, candidate, snapshots and valuation | `research.py`, operational-pipeline tests |
| Provider-to-outcome lineage | Implemented with protected, redacted audit API | migration 012, `GET /api/v1/audit/lineage/{run_id}`, API tests |
| Kimi research worker | Implemented as bounded manual workflow | `providers/research.py`, `RESEARCH_WORKERS.md` |
| OpenAI synthesis adapter | Implemented, disabled pending approved configuration and live debug | `providers/research.py`, tests |

## State, evidence and learning

| Requirement | Status | Evidence |
| --- | --- | --- |
| Exact candidate state lifecycle | Implemented | `domain.py` |
| Candidate transition actor/reason/evidence | Implemented | migration 003, `service.py` |
| Exact conditional-plan state lifecycle | Implemented | `plans.py` |
| Paper-ready/open transitions blocked in V1 | Implemented | `plans.py`, tests |
| Authenticated signal creation | Implemented as a separate operator action after approved-plan and freshness gates; scheduled pipeline performs eligibility only | `service.py`, `POST /api/v1/plans/{plan_id}/signal`, signal tests |
| Signal outcomes at 1h/close/1d/5d/20d/strategy | Implemented with actual observation times, benchmark lineage and unavailable-not-zero semantics | `outcomes.py`, signal lifecycle tests |
| Hit rate, false positives, drawdown and benchmarks | Implemented | `outcomes.py` |
| User approval/rejection evidence API | Implemented, protected | `POST /api/v1/feedback` |

## Command centre and operations

| Requirement | Status | Evidence |
| --- | --- | --- |
| SPY, QQQ, IWM, VIX, breadth | Implemented | `reports.py` |
| Yields, DXY, USDJPY, oil, gold, sectors, macro events | Implemented | `reports.py` |
| Supporting/contrary evidence and strategy controls | Implemented | `MarketRegime` |
| 13 dashboard routes | Implemented | `apps/dashboard`, dashboard verification and build |
| Runtime APIs for reports, screens, valuations, candidates, research, news, ownership, plans, signals, performance, watchlists | Implemented | `main.py` |
| Premarket, after-open, after-close, news, SEC, Telegram drain and weekend jobs | Callable and fixture-tested with same-window locks. After-open is truthfully scoped to Finviz refresh; after-close progresses outcomes, aggregates performance, stores a Chinese report and queues/sends Telegram. Executor remains not verified. | `config/scheduler_manifest.json`, `src/lmio/scheduler.py`, scheduler tests |
| Bayview OS write-back stage | Not in the executable pipeline; planned external governance integration only | `pipeline.py`, acceptance report |
| Telegram grouping, dedupe, rate-limit, queued release and bounded retry | Implemented | `telegram.py`, schema v5, tests |
| Telegram live delivery | Verified privately on 2026-07-31 | One Chinese non-trading alert sent; one attempt; identical repeat deduplicated; secrets remain Keychain-only |
| Live market/fundamental/revision provider | Pending approved provider/export | external gate |
| Protected runtime deployment | Pending CEO approval and deployment target | production gate |
| Operating, backup/recovery, deployment and troubleshooting guidance | Implemented | `OPERATIONS.md`, `BACKUP_RECOVERY.md`, `DEPLOYMENT.md` |
| Consistent SQLite backup and integrity verification | Implemented | `RuntimeStore.backup_to`, `tests/test_backup.py` |
| Offline V1 security review | Implemented; production review still gated | `SECURITY_REVIEW.md`, security and audit tests |

## Deferred by the governing V1 scope

- Options-flow data and unusual-options activation.
- Social-sentiment provider activation.
- Broker connectivity, orders, live trading and paper trading.
- Automatic purchase of any provider or service.

## Completion rule

Offline V1 can be declared code-complete only after Python and dashboard lint,
type checks, tests, build/import, security checks, dependency audits and replay
tests pass. Telegram private delivery is verified. Operational completion still
requires approved market-data and protected deployment debugging. Those
external gates must be reported as pending rather than simulated.
