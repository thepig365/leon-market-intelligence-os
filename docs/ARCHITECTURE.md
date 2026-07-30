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

Migration 003 adds normalised symbols, provider snapshots, candidate and plan
transition evidence, ownership events, signals, feedback, strategy performance
and watchlists. These tables cover the offline V1 decision-support workflow;
they are not an order-management system.

## State models

Candidates use:

```text
DISCOVERED -> FILTERED -> RESEARCHING -> WATCHING -> CONFIRMED
                                      \-> REJECTED / EXPIRED
```

Conditional plans use the governing state names, but the V1 safety guard blocks
entry into `PAPER_READY` and `PAPER_OPEN`:

```text
DRAFT -> WAITING_CONFIRMATION -> PAPER_READY -> PAPER_OPEN
   \-> INVALIDATED                         \-> CLOSED -> REVIEWED
```

Every persisted transition records time, actor, reason, previous/new state and
evidence URLs.
