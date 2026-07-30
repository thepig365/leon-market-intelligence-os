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
                              |
                 read-only server-side HTTP
                              |
LMIO dashboard
  Next.js / TypeScript / 13 governed views / no browser credentials
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

Migration 004 adds generic ingestion fingerprints so repeated SEC ownership
monitoring cannot duplicate the same parsed filing record. Structured ownership
records are derived deterministically from official 13F information tables,
Schedule 13D/13G documents and Form 4 XML; they remain confirmation evidence,
never an automatic trade trigger. Current 13F position values are interpreted
in the SEC-required nearest-dollar unit, and the information-table XML is
resolved from the official filing directory rather than the cover document.

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

## Dashboard

`apps/dashboard` is the primary V1 operator interface. It renders the 13
governed views from the Master Specification and reads LMIO through
server-side HTTP. Provider credentials and the administrator API key never
enter browser JavaScript. Missing or unavailable runtime data is shown as an
explicit safe-degradation state rather than invented content.

The minimal HTML routes served by FastAPI remain a diagnostic fallback for
runtime inspection. They are not the specification-aligned primary dashboard.
