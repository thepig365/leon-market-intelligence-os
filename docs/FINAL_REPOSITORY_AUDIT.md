# Final Repository Truth Audit

Audit date: 2026-08-02  
Branch: `codex/lmio-operational-acceptance`  
Audited head before RC1 work: `27d550e920d61aa1510bce724832553bcf83320d`

## Executive finding

LMIO is a substantial, test-backed research and decision-support implementation,
but it is not yet a production-accepted autonomous operating system. The code
contains a fixed 21-stage research pipeline, evidence-aware ranking, valuation,
research packages, conditional plans, outcome tracking, provider adapters,
Telegram delivery, protected APIs and a Chinese-first dashboard. Trading is
explicitly disabled and no broker/order package exists.

The largest remaining gap is operational evidence: the unattended executor,
isolated migrations 007–012, protected runtime, authorised provider reads,
Telegram delivery and three consecutive market days have not all been freshly
verified at this head. Those states must remain visibly separate from code and
fixture evidence.

## Repository and pull-request topology

Four Draft pull requests are open:

| PR | Head | Base | Purpose | Audit position |
|---|---|---|---|---|
| #1 | `agent/lmio-v1-foundation` | `main` | Original V1 foundation | Superseded by later stacked work; do not merge independently |
| #2 | `codex/lmio-human-readable-dashboard` | `main` | Human-readable private console | Active ancestor of later work |
| #3 | `codex/lmio-public-audit` | PR #2 head | Public audit view | Direct base of PR #4 |
| #4 | `codex/lmio-operational-acceptance` | PR #3 head | Operational remediation and RC1 acceptance | Current work and review gate |

PR #4 is mergeable and Draft. Its current base intentionally preserves the
stack. No PR is treated as approved or merged by this audit.

## Capability classification

### Implemented and test-backed

- fixed 21-stage canonical pipeline with per-stage persisted status;
- deterministic Top 10 ranking and evidence-gated Top 3 selection;
- quality, valuation, opportunity and timing scores kept distinct;
- Strict FCF, Normalised Owner Earnings and Multi-Model Fair Value;
- 11 strategy screens including the approved pattern-recognition strategy;
- same-run valuation, research-package and lineage references;
- conditional plans, authenticated operator approval and separate signal
  eligibility/creation boundaries;
- timestamped 1h, close, 1d, 5d and 20d outcome states with unavailable values
  kept distinct from zero;
- Finviz API/CSV, SEC EDGAR and official macro/news adapters;
- private Telegram webhook, bounded ticker queries, deduplicated outbox and
  retry-safe delivery;
- SQLite and Supabase stores, schema migrations through version 12, backup and
  recovery primitives;
- protected runtime reads, protected mutations, cron secret and fail-closed
  authentication;
- Chinese-first dashboard with 13 product sections and no raw JSON dumps;
- explicit synthetic/fixture provenance and a public, non-sensitive audit page.

### Implemented but not freshly live-verified at this head

- authorised Finviz refresh against the protected runtime;
- current SEC and official macro refresh evidence;
- private Telegram end-to-end send and query evidence;
- Supabase migrations 007–012 and service-role/RLS boundary;
- Vercel protected runtime/dashboard environment alignment;
- automatic executor process and all seven canonical scheduled jobs;
- live outcome horizons and three consecutive US market days.

### Deliberately disabled or deferred

- live trading, paper trading, broker connections and orders;
- unusual-options data provider and options-flow product UI;
- OpenAI research adapter until separately configured and verified;
- synthetic replay outside an explicit local/admin test mode;
- company investor-relations feeds without an explicit allowlist;
- Bayview OS write-back as a pipeline stage (it is planned external governance,
  not Stage 22).

## Placeholders, mock-only paths and incomplete surfaces

| Finding at audit start | Location | Classification | RC1 disposition |
|---|---|---|---|
| Synthetic META and replay data | `src/lmio/demo.py` | fixture-only | Keep isolated and visibly watermarked |
| `unusual-options` | `apps/dashboard/src/lib/navigation.ts` | deferred | Continue to show no provider/no data |
| `paper-trades` | same | intentionally disabled | Preserve no-trading boundary |
| Scheduler executor reports `not_verified` | `src/lmio/scheduler.py` | operational gap | Change only after unattended run evidence |
| Telegram application health reports configured, not live-ready | `src/lmio/health_console.py` | evidence gap | Bind display to persisted successful evidence |
| Vercel cron covered only two refresh endpoints | `vercel.json` | incomplete executor | Resolved in RC1: all seven manifest jobs mapped; live execution still unverified |
| Package version was `0.2.0` | `pyproject.toml`, `src/lmio/__init__.py` | stale release label | Resolved in RC1 as `1.0.0rc1`, without claiming production acceptance |
| Deployment prerequisite named migration 006 only | `docs/DEPLOYMENT.md` | stale documentation | Resolved in RC1: schema 12 and rehearsal/production gates separated |
| Dashboard lacked an operator acceptance workspace | `apps/dashboard/src/app` | incomplete frontend | Resolved in RC1 with protected `/acceptance` route |
| Feedback could be written but not reviewed in UI | `/api/v1/feedback`, dashboard | incomplete workflow | Resolved in RC1 with persisted decisions and history |
| Safe operator controls were API/CLI-only | runtime/dashboard | incomplete frontend | Resolved in RC1 with protected server-side controls and no browser secret |

The repository search found no unqualified `TODO` or `FIXME` implementation
markers. The material gaps are semantic and operational rather than comment
markers.

## Environment truth

Documented runtime variables include the safety flags, store selection,
Supabase secrets, read/admin/cron keys, SEC identity, Telegram credentials,
Finviz token and optional OpenAI configuration. Dashboard deployment also
requires `LMIO_API_BASE_URL`, the shared server-only read key and the two public
Supabase browser configuration values. The owner identity variable
`LMIO_OWNER_IDENTITY` exists in code but was not present in `.env.example` at
the start of this audit and must be documented.

No secret values were printed or copied during this audit.

## Dead, misleading or weak routes

- `/api/screens/run` delegates to synthetic replay and therefore remains
  unavailable unless explicit demo mode is enabled. It must not be presented as
  an operational screen control.
- `/api/valuation/{symbol}/run` falls back to the META fixture path and must not
  be exposed as a live arbitrary-symbol valuation control.
- `/api/options/{symbol}` correctly returns a deferred-state error and is not a
  dead promise.
- the dashboard catch-all section route is intentional and statically covers
  the 13 governed sections.

## Error-handling and safety observations

- provider refresh failures preserve prior data and return bounded errors;
- missing runtime data is rendered as empty/unavailable rather than invented;
- mutation and cron endpoints fail closed when their keys are absent;
- webhook queries reject wrong secrets and unapproved chats;
- runtime health is public but private evidence requires the read credential;
- the UI needs a clearer split between code, configuration, successful live
  verification, unattended operation, and operator acceptance. RC1 must add
  this evidence ladder.

## Release conclusion

The repository is suitable for RC1 engineering and operator-acceptance work on
PR #4. It is **not** yet suitable for a `Production Accepted` label. Protected
database migration, production deployment, unattended evidence, operator
acceptance and independent review remain separate gates.
