# Protected Deployment Guide

LMIO is not deployed by this repository foundation. Deployment is protected
because it introduces external access, credentials and operational data.

## Prerequisites

- Leon approves the target environment and production action.
- The target is private and access-controlled.
- No broker, order, live-trading or paper-trading integration exists.
- Environment values are stored in the platform secret manager, never Git.
- The database and recovery method are selected and rehearsed.
- Data-provider rights and usage limits are documented.
- The runtime and dashboard share an approved private access boundary.

## Required configuration

Safe flags:

```text
CAN_TRADE=false
LIVE_TRADING_ENABLED=false
PAPER_TRADING_ENABLED=false
```

Set `LMIO_ADMIN_API_KEY` for protected mutations. Optional SEC, Telegram and
OpenAI values remain blank until each integration is separately approved and
debugged. `LMIO_OPENAI_MODEL` must be an explicitly approved model snapshot.

Set `LMIO_API_BASE_URL` only in the dashboard server environment. It must point
to the private LMIO runtime. Do not expose `LMIO_ADMIN_API_KEY` or provider
credentials to the dashboard or any `NEXT_PUBLIC_*` variable.

## Release gate

Run:

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
git diff --check

cd apps/dashboard
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm audit
```

Also complete a dependency audit, schema migration rehearsal, backup/recovery
rehearsal and secret scan.

## Smoke test

1. Verify access control before supplying operational data.
2. Check `/health`, `/ready` and `/api/v1/providers/health`.
3. Confirm all trading flags are false.
4. Run only synthetic replay first.
5. Verify report, valuation, audit and outcome records are versioned.
6. Verify mutating endpoints reject a missing or wrong admin key.
7. Verify provider failures degrade safely.
8. Verify no secret appears in responses or logs.

## Rollback

Preserve the previous application artifact and database backup. Stop incoming
jobs, return traffic to the last verified artifact, and restore data only under
the tested recovery procedure. Do not force a schema downgrade over the only
copy of operational data.

Production deployment and its smoke-test evidence remain pending until Leon
approves the target and release.
