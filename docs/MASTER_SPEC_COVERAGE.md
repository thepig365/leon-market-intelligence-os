# LMIO Master Spec Coverage

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
| Authorised current-data export | Implemented with freshness, timezone, duplicate, size, row-count and completeness gates; external authorised export still pending | `providers/csv_snapshot.py`, `docs/AUTHORISED_DATA_IMPORT.md`, tests |
| Independent V1 strategy screens | Implemented | `screens.py` |
| Quality growth, revisions, institutional, activist, insider, QARP, PEAD, news, oversold, short squeeze | Implemented | deterministic combination rules and tests |
| Four dimension scoring | Implemented | `scoring.py` |
| Earnings revision breadth and EPS revision | Implemented | `screens.py`, tests |
| Official SEC monitoring | Implemented, external verification pending | `providers/sec.py`, `sec_monitor.py` |
| 13F, Schedule 13D/13G and Form 4 parsing | Implemented with bounded official-document fetch and ingestion dedupe | `sec_ownership.py`, migration 004, parser/monitor tests |
| News normalisation, dedupe and impact | Implemented | `news.py`, `news_plan.py` |
| Directional reaction windows, VWAP, opening range and gap retention | Implemented | `news_plan.py`, API and news-plan tests |
| Three valuation perspectives and sensitivity | Implemented for supported company types; multi-model output combines applicable DCF and approved market-multiple inputs | `valuation.py`, `routing.py` |
| Banks, REITs, unprofitable and cyclical routing | Safely blocked from generic DCF | `routing.py`, tests |
| Top 10 required fields | Implemented | `ScreenCandidate`, reports |
| Top 3 decision cards | Implemented | `DecisionCard`, reports |
| 15-field research package | Implemented | `research.py` |
| Kimi research worker | Implemented as bounded manual workflow | `providers/research.py`, `RESEARCH_WORKERS.md` |
| OpenAI synthesis adapter | Implemented, disabled pending approved configuration and live debug | `providers/research.py`, tests |

## State, evidence and learning

| Requirement | Status | Evidence |
| --- | --- | --- |
| Exact candidate state lifecycle | Implemented | `domain.py` |
| Candidate transition actor/reason/evidence | Implemented | migration 003, `service.py` |
| Exact conditional-plan state lifecycle | Implemented | `plans.py` |
| Paper-ready/open transitions blocked in V1 | Implemented | `plans.py`, tests |
| Signal outcomes at 1h/close/1d/5d/20d/strategy | Implemented | `outcomes.py` |
| Hit rate, false positives, drawdown and benchmarks | Implemented | `outcomes.py` |
| User approval/rejection evidence API | Implemented, protected | `POST /api/v1/feedback` |

## Command centre and operations

| Requirement | Status | Evidence |
| --- | --- | --- |
| SPY, QQQ, IWM, VIX, breadth | Implemented | `reports.py` |
| Yields, DXY, USDJPY, oil, gold, sectors, macro events | Implemented | `reports.py` |
| Supporting/contrary evidence and strategy controls | Implemented | `MarketRegime` |
| 13 dashboard routes | Implemented | `main.py`, API tests |
| Runtime APIs for reports, screens, valuations, candidates, research, news, ownership, plans, signals, performance, watchlists | Implemented | `main.py` |
| Continuous, premarket, after-open, after-close, weekend jobs | Defined and read-only | `config/hermes_jobs.json` |
| Telegram grouping, dedupe, rate-limit, queued release and bounded retry | Implemented | `telegram.py`, schema v5, tests |
| Telegram live delivery | Pending credentials and end-to-end debug | external gate |
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

Offline V1 can be declared code-complete only after lint, tests, build/import,
security checks, dependency audit and replay tests pass. Operational completion
also requires external SEC, Telegram, approved market-data and protected
deployment debugging. Those external gates must be reported as pending rather
than simulated.
