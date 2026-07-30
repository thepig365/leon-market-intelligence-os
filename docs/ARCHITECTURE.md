# LMIO V1 Architecture

## Boundary

```text
Bayview OS
  projects / work / decisions / evidence / knowledge / risks / handover
                              |
                 narrow authenticated writeback
                              |
LMIO runtime
  provider snapshots / universe / screens / evidence / valuations
  scores / conditional plans / alerts / outcomes / health
```

Bayview OS is canonical for project memory. LMIO is canonical for detailed
market-runtime evidence. No high-volume market table belongs in Bayview OS.

## Deterministic pipeline

```text
Provider adapters
  -> normalised immutable snapshots
  -> investable universe policy
  -> strategy-specific screens
  -> four independent scores
  -> research and valuation
  -> Top 10 / Top 3
  -> Chinese report / Telegram outbox / dashboard
  -> outcome tracking
```

Every calculation has a version. Missing values lower confidence and are never
silently replaced by AI. Re-running the pipeline appends a new run.

## Provider policy

Adapters return bounded health states: disabled, ready, degraded or
unavailable. Core logic consumes the LMIO domain model rather than provider
response formats. The first official adapter is read-only SEC EDGAR. Market and
fundamentals provider activation must pass a cost and terms review.

## Security

- Secrets exist only in environment variables or a managed secret store.
- Secret-bearing audit fields are recursively redacted.
- Health output reveals configuration presence, never values.
- Mutating HTTP routes require an administrator API key.
- No broker/order package exists.
- All trading and paper-trading flags are validated false at startup.

## Persistence

Development uses a versioned SQLite schema. Production may use PostgreSQL after
the production readiness gate. Financial, score, valuation, plan and outcome
history is append-only or versioned.
