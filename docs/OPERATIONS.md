# LMIO V1 Operations Manual

Operational claims require stored run evidence. A build or fixture replay is
not a successful scheduled market-data run. Canonical jobs live in
`config/scheduler_manifest.json` and execute through `lmio scheduled-job`.
The manifest uses fixed UTC slots. Each call acquires an atomic idempotency key
for the intended schedule window and records scheduled, started and completed
times, run ID where available, lock state and duplicate skips. The automatic
executor remains `not_verified` until an actual executor is deployed and
observed.

## Operating boundary

LMIO V1 is read-only market intelligence and decision support. It has no broker
adapter and cannot create an order. `CAN_TRADE`, `LIVE_TRADING_ENABLED` and
`PAPER_TRADING_ENABLED` must remain false.

## Start and inspect

```bash
uv sync --frozen --all-groups
uv run python -m lmio.cli status
uv run uvicorn lmio.main:app --host 127.0.0.1 --port 8000
```

Inspect `/health`, `/ready` and `/api/v1/providers/health`. A configured
provider is not healthy until a successful read-only verification has been
recorded.

## Routine jobs

`config/hermes_jobs.json` describes the broader continuous, premarket,
after-open, after-close and weekend operating model. The protected Vercel
runtime implements weekday Finviz and official-news refreshes through `vercel.json`. Vercel
sends `Authorization: Bearer <CRON_SECRET>` to the refresh endpoint. Preview
deployments do not run cron jobs; activation therefore remains a protected
production deployment action.

The safe local workflow is:

1. validate provider freshness and source attribution;
2. ingest a versioned snapshot;
3. run screens and valuations;
4. generate the Chinese report;
5. review evidence and warnings;
6. record outcomes later without overwriting the original run.

The automatic Finviz run performs steps 1–4 and then queues or sends the
Chinese Telegram brief. It preserves the previous successful run if Finviz is
unavailable. Use the admin-protected manual refresh endpoint for an additional
operator-requested update; do not poll more often than the provider licence and
rate limits permit.

The after-open job is deliberately named `after-open-finviz-refresh`: it only
performs the authorised Finviz refresh and concise observation delivery. It does
not claim to complete news-price verification. The after-close job progresses
due outcomes, aggregates strategy/horizon performance, stores a concise Chinese
report and queues or sends that report through the Telegram outbox.

The canonical pipeline has 21 executable stages. Bayview OS narrow write-back
is not an executable stage; it remains a planned external governance
integration. The pipeline performs signal eligibility checks but never creates
a signal automatically. A formal signal can only be created through the
admin-protected operator endpoint after the authenticated operator has approved
the same-run conditional plan.

The official-news run is separate and read-only. It collects allowlisted
Federal Reserve monetary-policy releases and BLS CPI, PPI, employment and JOLTS
releases. It also checks SEC filings for the configured symbols plus symbols in
the latest Top 10 when their CIK can be resolved from the official SEC ticker
directory. A failed feed is marked degraded without deleting prior news. Run it
locally with:

```bash
uv run python -m lmio.cli refresh-news
```

No news item creates an order. Company investor-relations feeds remain pending
because issuers do not expose one consistent official feed contract; they must
be onboarded with an explicit allowlisted mapping rather than guessed URLs.

The private Telegram bot also accepts bounded read-only queries from Leon's
approved chat:

- send `/status` to see the latest verified Finviz connection state;
- send a ticker such as `SNDK`, or `/quote SNDK`, to request a current
  single-symbol Finviz snapshot;
- send `/help` to see the supported commands.

Telegram signs webhook calls with `TELEGRAM_WEBHOOK_SECRET`. The runtime ignores
messages from every chat except `TELEGRAM_CHAT_ID`. A ticker query calls the
official Finviz API for that symbol; it does not invent missing fields, place an
order or enable paper/live trading.

The daily `telegram-webhook-ensure` job verifies that Telegram is still pointing
to `LMIO_PUBLIC_BASE_URL/api/v1/telegram/webhook` and restores that exact private
webhook if it has drifted. It never returns the bot token, webhook secret or
approved chat identifier to the dashboard.

The synthetic demo is for replay testing only:

```bash
uv run python -m lmio.cli demo-daily
uv run python -m lmio.cli meta-acceptance
```

Create a verified local backup using the procedure in `BACKUP_RECOVERY.md`.

## Provider failure

- Keep the last successful snapshot with its timestamp.
- Mark stale or missing fields; never silently substitute invented values.
- Reduce confidence when required evidence is absent.
- Do not mark configuration as ready merely because credentials exist.
- Telegram failure must preserve the outbox and must not interrupt core
  research.
- Each Telegram invocation makes at most one network attempt. Failed deliveries
  may be retried by a later invocation, up to three total attempts. Messages
  queued before credentials are configured become eligible for delivery after
  valid credentials are supplied.
- Research-worker failure must fall back to deterministic research packs.
- Finviz HTTP 429 triggers at most two waits and three total attempts. Other
  provider failures are recorded by error type only; the token and request URL
  are never written to logs.

## Local Telegram credential handling

The approved local operator setup stores the active token and authorised chat
identifier in macOS Keychain under dedicated LMIO service labels. Retrieve them
only at process start and inject them as `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. Do not copy either value into `.env`, source, logs,
screenshots, Bayview OS or issue/PR text.

The dedicated bot is private and cannot join groups. If a token appears in any
visible output, revoke it immediately in BotFather, replace the Keychain item
and repeat the private delivery check. A successful check must record delivery
state and attempt count without recording the secret or chat identifier.

## Troubleshooting

### Startup rejects trading flags

This is expected safety behaviour. Set all three trading flags to `false`. Do
not change the validator.

### Readiness says configured_not_verified

Configuration exists, but no successful live read has been proven. Run the
provider-specific read-only debug and record non-secret evidence.

### No report exists

In local development, run the synthetic replay. In a protected environment,
confirm an authorised data snapshot exists before running research.

### SQLite is locked or damaged

Stop all writers. Preserve the database file unchanged. Follow
`BACKUP_RECOVERY.md`; do not delete, overwrite or rebuild the only copy.

### Mutating API returns 401/503

Confirm `LMIO_ADMIN_API_KEY` exists only in the server environment and the
client sends `X-LMIO-Key`. Never paste the key into logs or source.

## Evidence and escalation

Record run time, commit SHA, data timestamp, provider status, warnings and test
results. Escalate to Leon only for credentials, spending, protected
production, privacy disclosure, live-trading scope or a material product
decision.
