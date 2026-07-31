# Protected Deployment Guide

LMIO uses two private Vercel projects sourced from the same repository:

1. repository root: FastAPI runtime through `api/index.py`;
2. `apps/dashboard`: Next.js operator dashboard.

The feature branch may create review deployments. Production remains gated by
Leon and the rule that the implementing agent cannot approve or merge its own
pull request.

## Prerequisites

- Leon approves the target environment and production action.
- The target is private and access-controlled.
- No broker, order, live-trading or paper-trading integration exists.
- Environment values are stored in the platform secret manager, never Git.
- The database and recovery method are selected and rehearsed.
- Data-provider rights and usage limits are documented.
- The runtime and dashboard share an approved private access boundary.
- Migration `006_supabase_runtime.sql` has been applied to the approved Bayview
  Supabase project and its RLS/privilege boundary has been verified.

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

Runtime environment:

```text
LMIO_ENVIRONMENT=production
LMIO_STORE_BACKEND=supabase
SUPABASE_URL=<approved project URL>
SUPABASE_SERVICE_ROLE_KEY=<server secret>
LMIO_READ_API_KEY=<random shared server secret>
TELEGRAM_BOT_TOKEN=<dedicated private bot token>
TELEGRAM_CHAT_ID=<approved Leon private chat>
TELEGRAM_WEBHOOK_SECRET=<random webhook verification secret>
CAN_TRADE=false
LIVE_TRADING_ENABLED=false
PAPER_TRADING_ENABLED=false
```

Dashboard environment:

```text
LMIO_API_BASE_URL=<review or production runtime URL>
LMIO_READ_API_KEY=<same shared server secret>
NEXT_PUBLIC_SUPABASE_URL=<approved project URL>
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<approved publishable key>
```

`LMIO_API_BASE_URL` and `LMIO_READ_API_KEY` are read only by the dashboard
server. Never expose `SUPABASE_SERVICE_ROLE_KEY`, `LMIO_READ_API_KEY`,
`LMIO_ADMIN_API_KEY` or provider credentials through a `NEXT_PUBLIC_*`
variable.

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

1. Verify an unauthenticated dashboard request redirects to `/sign-in`.
2. Verify an approved Bayview identity can sign in and an unapproved identity
   is rejected.
3. Check runtime `/health` without a credential.
4. Confirm runtime `/ready` and `/api/v1/providers/health` return 401 without
   `LMIO_READ_API_KEY` and succeed with the correct server credential.
5. Confirm all trading flags are false.
6. Run only synthetic replay first.
7. Verify report, valuation, audit and outcome records are versioned.
8. Verify mutating endpoints reject a missing or wrong admin key.
9. Verify provider failures degrade safely.
10. Verify no secret appears in responses or logs.
11. Verify Telegram rejects a wrong webhook secret and an unapproved chat.
12. From Leon's approved private chat, send `/status` and one ticker symbol;
    confirm both responses arrive and the ticker response cites Finviz.

## Rollback

Preserve the previous application artifact and database backup. Stop incoming
jobs, return traffic to the last verified artifact, and restore data only under
the tested recovery procedure. Do not force a schema downgrade over the only
copy of operational data.

Production deployment and its smoke-test evidence remain pending until Leon
approves the target and release and independently merges the reviewed PR.
