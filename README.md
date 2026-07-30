# Leon Market Intelligence OS

LMIO is a Chinese-first, evidence-backed research and decision-support runtime
for United States equities. It ranks research candidates, preserves their
evidence, calculates three distinct valuation perspectives, produces quiet
Chinese reports, and tracks what happened afterwards.

Bayview OS remains the only project-memory and governance layer. LMIO stores
detailed market runtime data and writes back only concise status, decision and
evidence references. It does not create a duplicate project-memory system.

## Current implemented capability

- reproducible investable-universe rules;
- ten independent V1 strategy screens covering quality growth, revisions,
  institutional accumulation, activist catalysts, insider value, QARP, PEAD,
  verified news, oversold reversal and short-squeeze combinations;
- independent quality, valuation, opportunity and timing scores;
- explicit missing-data confidence reduction;
- Top 10 and Top 3 ranking without forcing an opportunity;
- Strict FCF, Normalised Owner Earnings and Multi-Model Fair Value views;
- META-shaped high-growth/high-CapEx acceptance fixture;
- official SEC EDGAR read-only adapter and data-contract tests;
- structured 13F, Schedule 13D/13G and Form 4 ownership parsing;
- bounded, freshness-checked and deduplicated authorised CSV ingestion;
- official-source news deduplication and impact scoring;
- directional reaction confirmation using abnormal return, relative volume,
  VWAP, opening-range structure and gap retention;
- evidence-audited candidate and conditional-plan state machines;
- Chinese daily brief and grouped, deduplicated, rate-limited Telegram outbox;
- append-only/versioned local SQLite runtime store;
- multi-horizon signal outcomes and benchmarked strategy performance;
- health, readiness and provider status;
- responsive read-only FastAPI fallback command centre;
- Chinese-first Next.js/TypeScript dashboard with all 13 required sections;
- protected mutating HTTP endpoints;
- structured audit logging with secret redaction;
- optional evidence-only OpenAI Responses API adapter, disabled by default;
- documented human-mediated Kimi research workflow;
- protected deployment, operations and backup/recovery runbooks;
- private GitHub quality checks for lint, formatting, tests and dependency
  vulnerabilities.

The bundled demonstration is synthetic replay data. It is clearly labelled and
must not be interpreted as current market information.

## Safety boundaries

LMIO V1 has no broker adapter or order module. Startup is rejected if any of
these values is true:

- `CAN_TRADE`
- `LIVE_TRADING_ENABLED`
- `PAPER_TRADING_ENABLED`

News, scores, Telegram, AI output and conditional plans cannot place an order.
Changing this boundary is outside LMIO V1 and requires a separate Leon decision.

## Local setup

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run uvicorn lmio.main:app --reload
```

Run the trusted local demonstrations:

```bash
uv run python -m lmio.cli demo-daily
uv run python -m lmio.cli meta-acceptance
uv run python -m lmio.cli status
```

An approved current-market export can be imported without coupling the core
system to a vendor:

```bash
uv run python -m lmio.cli import-csv --file /approved/path/snapshot.csv
```

The input must satisfy `docs/AUTHORISED_DATA_IMPORT.md`. A successful parse is
not evidence that the upstream provider is authorised; Leon's provider decision
and the export's provenance remain required.

Then open:

- FastAPI fallback command centre: `http://127.0.0.1:8000/`
- API reference: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`
- readiness: `http://127.0.0.1:8000/ready`

Run the required Next.js dashboard in a second terminal:

```bash
cd apps/dashboard
cp .env.example .env.local
npm ci
npm run dev
```

Then open `http://127.0.0.1:3000`. The dashboard performs server-side,
read-only requests to FastAPI and never receives provider or administrator
credentials.

HTTP mutations require `LMIO_ADMIN_API_KEY` and the `X-LMIO-Key` request
header. The trusted local CLI does not expose a remote mutation surface.

## Optional integrations

- `SEC_USER_AGENT`: a fair-access identity required by the SEC;
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`: priority alert delivery;
- `OPENAI_API_KEY` and `LMIO_OPENAI_MODEL`: optional server-side,
  evidence-only research synthesis; both are blank and inactive by default;
- `LMIO_ADMIN_API_KEY`: protects mutating HTTP endpoints.

LMIO never reports an integration as working merely because its configuration
exists. A successful read-only verification is required.

The exact V1 requirement-to-evidence map is maintained in
[`docs/V1_ACCEPTANCE.md`](docs/V1_ACCEPTANCE.md). External SEC, Telegram,
current-market data and protected production checks remain visibly pending
until their real verification succeeds.

The broader governing specification is tracked in
[`docs/MASTER_SPEC_COVERAGE.md`](docs/MASTER_SPEC_COVERAGE.md).

Operator references:

- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/BACKUP_RECOVERY.md`](docs/BACKUP_RECOVERY.md)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/RESEARCH_WORKERS.md`](docs/RESEARCH_WORKERS.md)
- [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md)
- [`docs/COMPLETION_AUDIT.md`](docs/COMPLETION_AUDIT.md)
- [`apps/dashboard/README.md`](apps/dashboard/README.md)

## Data boundary

The local versioned SQLite store is the development default. Financial,
screening, valuation, report and outcome runs append new records; recalculation
does not silently overwrite history. Production PostgreSQL/Supabase activation
and deployment remain protected steps.
