# LMIO V1 Security Review

Reviewed: 2026-07-30  
Scope: offline V1 runtime at the draft-review branch

## Result

No blocker was found in the offline V1 boundary. This is not production
authorization. Internet exposure, operational credentials and real data require
the protected deployment gate and a new environment-level review.

## Verified controls

- There is no broker adapter, order module, live trading or paper trading.
- Startup rejects `CAN_TRADE`, `LIVE_TRADING_ENABLED` or
  `PAPER_TRADING_ENABLED` when true.
- Every mutating FastAPI route uses `require_admin`.
- Mutations are disabled when `LMIO_ADMIN_API_KEY` is absent.
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

## Threats and controls

| Threat | V1 control | Remaining production action |
| --- | --- | --- |
| Unauthorised mutation | fail-closed admin header guard | private network/access layer, key rotation and rate limits |
| Secret leakage | server environment, `SecretStr`, audit redaction | platform secret manager and log inspection |
| Fabricated provider readiness | disabled/configured-not-verified states | record successful read-only provider checks |
| Prompt/model overreach | evidence-only schema; deterministic calculations remain authoritative | approved model, budget and adversarial eval |
| Data loss | versioned store and verified online backup | encrypted remote backups and recovery rehearsal |
| Stale or false market facts | source URLs, timestamps and confidence reduction | authorised current provider and freshness monitoring |
| Trading-boundary erosion | three startup locks and no order module | separate future architecture and CEO decision |

## Open external gates

1. Telegram credential handling and delivery verification.
2. Authorised live-data rights, freshness and failure testing.
3. Private production identity, network, TLS and platform configuration.
4. Production backup storage, retention, encryption and recovery rehearsal.
5. Exact desktop/mobile production acceptance testing.

## Review trigger

Repeat this review before production deployment and whenever an authentication
method, external provider, model, database, alert channel or trading boundary
changes.
