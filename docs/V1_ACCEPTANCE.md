# LMIO V1 Acceptance Record

This record maps the governing Master Specification Definition of Done to
implemented evidence. It distinguishes deterministic product completion from
external integrations that require credentials or a successful live read.

| # | Requirement | Implementation evidence | Automated evidence | State |
|---|---|---|---|---|
| 1 | Reproducible investable universe | `src/lmio/universe.py` | `tests/test_universe.py` | Pass |
| 2 | Quality-growth and earnings-momentum screens | `src/lmio/screens.py` | `tests/test_scoring_and_screens.py` | Pass |
| 3 | Candidate strategy and evidence retained | `src/lmio/domain.py`, `src/lmio/store.py` | `tests/test_store_and_service.py` | Pass |
| 4 | Top 10 and Top 3 without forced trade | `src/lmio/service.py`, `src/lmio/reports.py` | `tests/test_reports.py` | Pass |
| 5 | Three distinct valuation perspectives | Strict FCF, Normalised Owner Earnings and a component-audited multi-model view using applicable DCF/multiple inputs | `tests/test_valuation.py` | Pass |
| 6 | Assumptions and confidence displayed | `src/lmio/valuation.py`, dashboard | `tests/test_valuation.py` | Pass |
| 7 | Official news and SEC monitoring | SEC read-only adapter and monitor; official-source news contract | `tests/test_sec_provider.py`, `tests/test_sec_monitor.py`, `tests/test_news.py`; 2026-07-30 fair-access read | Pass |
| 8 | Deduplicated Chinese Telegram reports with bounded retries | `src/lmio/telegram.py`, `src/lmio/reports.py` | `tests/test_telegram.py`, `tests/test_reports.py`, schema v5 upgrade tests; 2026-07-31 private live-delivery check | Pass |
| 9 | System and provider health | `/health`, `/ready`, command centre | `tests/test_health.py`, `tests/test_api.py` | Pass |
| 10 | Outcomes stored for evaluation | `src/lmio/outcomes.py`, versioned store | `tests/test_outcomes.py` | Pass |
| 11 | Automated core-calculation tests | `tests/` | `uv run pytest` | Pass |
| 12 | No live-trading capability | No broker/order module; three flags locked false | `tests/test_config.py`, `tests/test_hermes_manifest.py` | Pass |
| 13 | Secrets protected | environment-only secrets, redacted audit, protected mutation API | `tests/test_audit.py`, `tests/test_security.py` | Pass |
| 14 | Missing data lowers confidence | scoring and research confidence policies | `tests/test_scoring_and_screens.py`, `tests/test_research.py` | Pass |
| 15 | META reported-FCF vs normalised economics | reproducible acceptance fixture and CLI | `tests/test_valuation.py` | Pass |
| 16 | Bounded Kimi/OpenAI research workers | manual Kimi packet; server-only OpenAI adapter disabled by default | `tests/test_research_workers.py` | Pass |
| 17 | Operations, deployment and recovery | protected runbooks plus verified non-destructive SQLite backup | `tests/test_backup.py`; isolated recovery rehearsal | Pass |
| 18 | Offline security review | fail-closed mutations, redaction, no trading and external gate review | `SECURITY_REVIEW.md`; security/audit tests | Pass |
| 19 | Structured SEC ownership evidence | deterministic 13F, Schedule 13D/13G and Form 4 parsers with official-host allowlist and ingestion dedupe | `tests/test_sec_ownership.py`, `tests/test_sec_monitor.py`, `tests/test_sec_provider.py`; 2026-07-30 AAPL/META refresh | Pass |
| 20 | News reaction structure | directional abnormal return, relative volume, VWAP, opening-range and gap-retention gates | `tests/test_news_plan.py`, `tests/test_api.py` | Pass |
| 21 | Authorised current-data ingestion | provider-neutral CSV and official Finviz Elite API adapters, immutable snapshot persistence, dedupe, freshness, retry and completeness gates | `tests/test_csv_provider.py`, `tests/test_finviz_api_provider.py`, `tests/test_store_and_service.py` | Pass; authorised live API refresh pending |
| 22 | Next.js/TypeScript operator dashboard | 13 governed Chinese-first views, server-side read-only runtime access and safe degradation | `apps/dashboard/scripts/verify-dashboard.mjs`; dashboard lint, typecheck and build | Pass |

## Verification commands

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
git diff --check
uv export --frozen --no-dev --no-emit-project --output-file requirements-audit.txt
uvx pip-audit -r requirements-audit.txt

cd apps/dashboard
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm audit
```

## External acceptance gates

These are deliberately not represented as complete until a successful
read-only or production test is recorded:

1. Current-market ingestion from an authorised export or approved provider.
2. Protected production deployment and production smoke test.

No paid service, provider subscription, external publication or trading
capability is activated by V1.

## Telegram live verification

On 2026-07-31, the approved private `LMIO Alert Bot` delivered one Chinese
non-trading test alert to Leon's private chat through the production Telegram
Bot API. Group joining is disabled. The active bot token and authorised chat
identifier are stored only in the local macOS Keychain and were injected into
the test process; neither value is committed or recorded in Bayview OS.

The delivery record is `sent` with one attempt. Repeating the identical
operation did not create or send a second message, confirming live
deduplication. All three trading flags remained false.

## SEC live verification

On 2026-07-30, the approved fair-access identity completed a successful
read-only refresh against official SEC EDGAR endpoints. The bounded AAPL/META
watchlist checked 50 recent filings and stored 33 deduplicated filing events
plus 92 structured ownership events in the ignored local development store.
No contact identity or credential is committed to the repository.
