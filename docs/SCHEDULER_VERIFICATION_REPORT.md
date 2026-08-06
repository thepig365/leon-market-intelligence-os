# Scheduler Verification Report

Status: **configured_not_verified**

## Configuration

The canonical manifest declares seven jobs and Vercel cron configuration now
maps each job to `/api/v1/scheduler/{job-id}` at the same UTC slot:

1. premarket data and screening;
2. after-open Finviz refresh;
3. after-close outcomes and report;
4. official-news refresh;
5. SEC refresh;
6. Telegram outbox drain;
7. weekend strategy/data-quality review.

Every invocation requires `CRON_SECRET`, uses a manifest allowlist, acquires a
same-window idempotency lock and stores start/end/status evidence. Unknown jobs
are rejected. Preview deployments do not run Vercel cron.

## Verified

- manifest parsing and UTC scheduling;
- duplicate-window suppression;
- successful/failed/skipped event recording;
- error preservation and no trading side effect;
- protected endpoint configuration.

## Not yet verified

- a deployed unattended executor process;
- all seven jobs completing in the protected environment;
- three consecutive US trading days;
- daylight-saving behaviour observed in real operation;
- alerting after a protected-job failure.

The dashboard must continue to show `configured_not_verified` until those
records exist.
