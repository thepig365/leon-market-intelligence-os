# LMIO Operational Acceptance Report

Date: 2026-08-02  
Branch: `codex/lmio-operational-acceptance`  
Starting commit: `369fa1c29448782eea27cd5f47728ec6e4836227`  
Decision owner: Leon  
State: **Draft — independent review required; not operationally accepted**

## Executive summary

LMIO now has one fail-closed, evidence-bearing 22-stage research pipeline. It
keeps authorised, synthetic and fixture provenance separate; evaluates Top 3
eligibility rather than forcing three names; routes unsupported valuations to
appropriate methods; records source-linked research, plans, signals, outcomes,
provider health and scheduler history; and exposes a Chinese operator console
and private Telegram query interface. No broker, order, live-trading or
paper-trading capability exists.

Code existence and automated verification are complete for the approved P0 and
most P1/P2 controls. Operational acceptance remains blocked by the explicitly
external gates below. In particular, this report does not describe a fixture,
build or endpoint as proof of a live scheduled service.

## Six-level evidence vocabulary

1. **Code exists** — implementation is present.
2. **Automated tests pass** — deterministic checks pass locally.
3. **Fixture replay succeeds** — authorised-style or synthetic evidence works,
   but is not live market proof.
4. **Real authorised external data succeeds** — redacted live provider evidence
   exists.
5. **Scheduled execution succeeds** — unattended executor evidence exists.
6. **Leon can use the workflow** — operator acceptance is recorded.

## Completion matrix

| Area | Code | Tests | Fixture | Live authorised | Scheduled | Leon usable |
|---|---:|---:|---:|---:|---:|---:|
| Fail-closed reads and roles | Yes | Yes | Yes | Pending smoke test | N/A | Pending |
| Provenance isolation | Yes | Yes | Yes | Pending live refresh | Pending | Pending |
| Top 10 / Top 3 eligibility | Yes | Yes | Yes | Pending live run | Pending | Pending |
| SEC fault tolerance | Yes | Yes | Yes | Prior bounded read recorded; new run pending | Pending | Pending |
| Finviz ingestion | Yes | Yes | Yes | Credentialed run pending | Pending | Pending |
| 22-stage pipeline | Yes | Yes | Yes | Pending | Pending | Pending |
| Valuation routing | Yes | Yes | Yes | Current-company set pending | N/A | Pending |
| 15-field research | Yes | Yes | Yes | Pending | Pending | Pending |
| News + stored price confirmation | Yes | Yes | Yes | Pending | Pending | Pending |
| Signals / outcomes / performance | Yes | Yes | Yes | Pending horizon evidence | Pending | Pending |
| Telegram interface | Yes | Yes | Yes | Prior private delivery recorded | Drain schedule pending | Partial |
| Dashboard and System Health | Yes | Yes | Build passes | Production smoke pending | N/A | Pending |
| Bayview OS write-back | Boundary documented | Yes | N/A | Not implemented | N/A | Planned |

## Functional evidence

- Canonical pipeline: `src/lmio/pipeline.py`; manifest:
  `config/scheduler_manifest.json`; scheduler: `src/lmio/scheduler.py`.
- Immutable runtime evidence: schema versions 7–11 and `src/lmio/store.py`.
- Provenance isolation: operational latest views exclude synthetic and fixture
  records; dashboard watermarks non-operational data.
- Top 3: `src/lmio/top3.py` persists eligibility state and structured blocking
  reasons; no forced selection.
- Research: `src/lmio/research.py` produces the governed 15-field package with
  evidence classifications.
- News: `src/lmio/news_price.py`; the analysis API no longer accepts a
  client-supplied price reaction and only creates a draft plan from a persisted,
  complete confirmation.
- Plans: stored snapshot reference, expiry, authenticated creator, transition
  actor, time and run ID are required.
- Telegram: allowlisted chat, concise Chinese commands, freshness warning,
  atomic outbox claim, bounded retry and terminal failure state.
- Health: application, provider, freshness, pipeline and safety layers are
  derived from runtime evidence.

## Database migrations

- `007_provenance_isolation.sql`
- `008_runtime_diagnostics.sql`
- `009_operational_pipeline.sql`
- `010_scheduler_and_telegram_claims.sql`
- `011_news_price_evidence.sql`

These migrations are additive. They have **not** been applied to protected
production by this task because that is a separate production approval gate.

## Verification results

Passed on 2026-08-02:

```text
Python Ruff: passed
Python pytest: passed (full suite)
Dashboard ESLint: passed
Dashboard type check: passed
Dashboard contract test: passed (13 modules)
Dashboard production build: passed
git diff --check: passed
```

## Evidence by acceptance topic

- Top 10 / Top 3: fixture evidence in `tests/test_store_and_service.py` and
  `tests/test_top3.py`; real current run pending.
- Research package: `tests/test_research.py`; real selected-company package pending.
- Telegram: contract, retry, rate limit and atomic-claim tests pass; private
  historical live delivery is documented, but this branch needs a fresh smoke test.
- Outcomes: all five horizons and unknown-versus-zero semantics are tested;
  live 1h/close/1d progression is pending.
- Failure recovery: Finviz, SEC per-filing, RSS, stale evidence, missing valuation,
  Telegram and unavailable outcome paths fail closed in automated tests.
- Security: missing/incorrect credentials are rejected, actors come from verified
  identity, secrets use server-side secret-aware settings, trading flags are
  immutable false, and no broker/order package or endpoint exists.

## Live and scheduled blockers

1. A redacted Finviz refresh using currently authorised credentials.
2. Protected preview/production smoke tests for read rejection and dashboard login.
3. Additive Supabase migrations and RLS verification in the protected project.
4. Three consecutive US trading days of unattended executor evidence. The report
   date is a Sunday, so this cannot truthfully be completed now.
5. Real Top 10 and justified Top 3/no-Top-3 output from those runs.
6. Automatic 1h, close and 1d outcome progression.
7. Leon operator acceptance and independent reviewer verdict.

Exact operator commands are documented in `docs/OPERATIONS.md`. Credentials,
licensed rows and private Telegram content are intentionally absent here.

## Remaining risks

- Runtime configuration or provider licensing may differ from local tests.
- Scheduled evidence does not exist until the executor is deployed and observed.
- A live Top 3 may correctly remain unavailable if financial or valuation evidence
  is incomplete; that is a valid fail-closed result, not a defect.
- Supabase restore rehearsal and RLS checks must be run against an isolated target
  before any production acceptance claim.

## Governance and deployment state

- Deployment: not performed by this task.
- Merge: prohibited pending Leon and independent review.
- Bayview write-back: only this milestone, blockers, commit/PR and evidence links
  may be recorded; no market data or detailed runtime logs belong in Bayview OS.

**No live trading, paper trading, broker connection or order-execution capability was added.**
