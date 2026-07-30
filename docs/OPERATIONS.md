# LMIO V1 Operations Manual

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

`config/hermes_jobs.json` defines continuous, premarket, after-open,
after-close and weekend schedules. The manifest is descriptive in V1; enabling
an external scheduler is a protected deployment action.

The safe local workflow is:

1. validate provider freshness and source attribution;
2. ingest a versioned snapshot;
3. run screens and valuations;
4. generate the Chinese report;
5. review evidence and warnings;
6. record outcomes later without overwriting the original run.

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
- Research-worker failure must fall back to deterministic research packs.

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
