# LMIO V1 Security Review

Reviewed: 2026-07-31
Scope: protected review deployment architecture at the draft-review branch

## Result

No blocker was found in the implementation boundary. This is not production
authorization. The review deployment must still pass authentication, RLS,
secret and recovery acceptance checks before production approval.

## Verified controls

- There is no broker adapter, order module, live trading or paper trading.
- Startup rejects `CAN_TRADE`, `LIVE_TRADING_ENABLED` or
  `PAPER_TRADING_ENABLED` when true.
- Every mutating FastAPI route uses `require_admin`.
- Mutations are disabled when `LMIO_ADMIN_API_KEY` is absent.
- All runtime routes except `/health` and `/favicon.ico` require a distinct
  constant-time checked server credential.
- The dashboard reuses active Bayview private-beta claims and does not create a
  second identity system.
- Supabase runtime tables use an isolated `lmio_*` namespace with RLS enabled,
  no browser policies and revoked anonymous/authenticated privileges.
- The service-role key remains only in the FastAPI server environment.
- Credential comparison uses constant-time comparison.
- Secrets are environment-only and `.env` is excluded from Git.
- Health output exposes booleans and states, not secret values.
- Structured audit fields matching passwords, tokens, credentials,
  authorization, cookies, secrets or API keys are recursively redacted.
- Provider configuration is not represented as successful verification.
- The OpenAI adapter is server-side, disabled by default, uses `store: false`,
  enables no tools and cannot create an order.
- Kimi output must pass the bounded research schema and remains draft research.
- SQLite backup refuses overwrite and verifies integrity before reporting
  success.
- Production dependency audit reported no known published vulnerabilities.
- The dedicated private Telegram bot has group joining disabled. Its active
  token and authorised chat identifier are stored only in macOS Keychain and
  were injected into a single test process. A previously displayed token was
  revoked before use; no active Telegram secret is stored in source, logs,
  Bayview OS or committed environment files.

## Threats and controls

| Threat | V1 control | Remaining production action |
| --- | --- | --- |
| Unauthorised read | Bayview identity plus server-to-server read key | review-deployment authentication acceptance |
| Unauthorised mutation | fail-closed admin header guard | key rotation and rate limits |
| Secret leakage | server environment, `SecretStr`, audit redaction | platform secret manager and log inspection |
| Fabricated provider readiness | disabled/configured-not-verified states | record successful read-only provider checks |
| Prompt/model overreach | evidence-only schema; deterministic calculations remain authoritative | approved model, budget and adversarial eval |
| Data loss | versioned store and verified online backup | encrypted remote backups and recovery rehearsal |
| Stale or false market facts | source URLs, timestamps and confidence reduction | authorised current provider and freshness monitoring |
| Trading-boundary erosion | three startup locks and no order module | separate future architecture and CEO decision |

## Open external gates

1. Authorised live-data rights, freshness and failure testing.
2. Review deployment identity, TLS and platform configuration.
3. Supabase schema/RLS and server-only key verification.
4. Production backup storage, retention, encryption and recovery rehearsal.
5. Exact desktop/mobile production acceptance testing.

## Review trigger

Repeat this review before production deployment and whenever an authentication
method, external provider, model, database, alert channel or trading boundary
changes.
