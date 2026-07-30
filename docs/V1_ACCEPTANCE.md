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
| 7 | Official news and SEC monitoring | SEC read-only adapter and monitor; official-source news contract | `tests/test_sec_provider.py`, `tests/test_sec_monitor.py`, `tests/test_news.py` | Live verification pending |
| 8 | Deduplicated Chinese Telegram reports | `src/lmio/telegram.py`, `src/lmio/reports.py` | `tests/test_telegram.py`, `tests/test_reports.py` | Delivery verification pending |
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
| 19 | Structured SEC ownership evidence | deterministic 13F, Schedule 13D/13G and Form 4 parsers with official-host allowlist and ingestion dedupe | `tests/test_sec_ownership.py`, `tests/test_sec_monitor.py`, `tests/test_sec_provider.py` | Pass; live read pending |
| 20 | News reaction structure | directional abnormal return, relative volume, VWAP, opening-range and gap-retention gates | `tests/test_news_plan.py`, `tests/test_api.py` | Pass |
| 21 | Authorised current-data ingestion | provider-neutral CSV adapter, immutable snapshot persistence, dedupe, freshness and completeness gates | `tests/test_csv_provider.py`, `tests/test_store_and_service.py` | Pass; authorised real export pending |

## Verification commands

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
git diff --check
uv export --frozen --no-dev --no-emit-project --output-file requirements-audit.txt
uvx pip-audit -r requirements-audit.txt
```

## External acceptance gates

These are deliberately not represented as complete until a successful
read-only or delivery test is recorded:

1. SEC fair-access live read using an approved contact identity.
2. Telegram delivery using an approved bot token and chat identifier.
3. Current-market ingestion from an authorised export or approved provider.
4. Protected production deployment and production smoke test.

No paid service, provider subscription, external publication or trading
capability is activated by V1.
