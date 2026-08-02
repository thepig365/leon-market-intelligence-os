# Codex Master Start Instruction

## Create Leon Market Intelligence OS Using Bayview OS as Its Persistent Project Memory

**Owner:** Leon  
**Date:** 30 July 2026  
**Target project:** Leon Market Intelligence OS  
**Project abbreviation:** LMIO  
**Operating system of record:** Bayview Enterprise Operating System  
**Known repository:** `thepig365/leon-ai-enterprise`  
**Primary product specification:** `LEON_MARKET_INTELLIGENCE_OS_MASTER_SPEC.md`

---

## 1. Your Assignment

Take ownership of creating Leon Market Intelligence OS as a formal project governed by the existing Bayview Enterprise Operating System.

Do not treat LMIO as a temporary coding session. Do not rely on chat history as project memory. Bayview OS must become the durable system of record for:

- project identity;
- objective and scope;
- decisions;
- implementation phases;
- work items;
- progress;
- blockers;
- evidence;
- research;
- source documents;
- architecture;
- tests;
- deployments;
- operating instructions;
- unresolved questions;
- handovers;
- future changes.

The outcome must be:

```text
LMIO Product and Services
        ↕
LMIO Repository / Runtime
        ↕
Bayview OS Project Memory and Governance
```

Bayview OS must be able to tell Leon and any future Codex session:

1. What LMIO is;
2. Why it is being built;
3. What has been decided;
4. What is currently being built;
5. What has been completed;
6. What evidence proves completion;
7. What remains;
8. What is blocked;
9. What should happen next;
10. Which source document governs the answer.

---

## 2. Governing Source Documents

Use these documents in this order:

1. `LEON_MARKET_INTELLIGENCE_OS_MASTER_SPEC.md`
2. This instruction
3. Existing Bayview OS architecture and repository conventions
4. Existing Bayview OS decisions and implementation records
5. New Architecture Decision Records created during implementation

The LMIO Master Specification governs product scope, strategy, safety and Definition of Done.

This instruction governs how LMIO must be created and remembered through Bayview OS.

Do not silently change either document.

If implementation reveals a genuine conflict:

1. record the conflict in Bayview OS;
2. explain the impact;
3. propose the smallest resolution;
4. ask Leon only if the decision materially changes product scope, cost, legal/risk exposure or delivery.

Routine engineering choices should be made and documented without repeatedly interrupting Leon.

---

## 3. Hard Product Boundaries

The following are locked:

- default user-facing language is Chinese;
- the initial market is United States equities;
- V1 is a research and decision-support system;
- V1 must not execute live trades;
- news alone cannot trigger an order;
- social-media information alone cannot trigger an order;
- Telegram is the priority alert channel;
- the Dashboard contains complete evidence and history;
- Kimi is a research worker, not the system controller;
- Hermes is the intended 24/7 orchestration layer;
- deterministic Python code performs calculations, valuation, scoring and risk rules;
- intrinsic value uses three separate perspectives;
- paid services require Leon's approval before activation;
- Bayview OS is the persistent project memory and governance system;
- no duplicate standalone memory framework is to be created inside LMIO.

Initial runtime flags must include:

```text
CAN_TRADE=false
LIVE_TRADING_ENABLED=false
PAPER_TRADING_ENABLED=false
```

Paper trading is a later phase and must require an explicit phase transition.

---

## 4. Start With Discovery, Not Coding

Before changing code, inspect the actual state of Bayview OS.

### 4.1 Repository discovery

Inspect:

- repository structure;
- active branch;
- working-tree status;
- recent commits;
- open or merged work related to AEO-006, AEO-007 and AEO-008;
- documentation;
- `AGENTS.md`;
- README files;
- architecture decision records;
- environment templates;
- database migrations;
- Supabase configuration;
- tests;
- deployment configuration;
- project/work/evidence/knowledge APIs;
- UI routes;
- authentication and authorisation;
- health endpoints;
- existing project records.

Do not assume that previously reported PRs are merged. Verify actual repository state.

Do not overwrite unrelated user changes.

### 4.2 Existing Bayview OS capabilities

Determine whether Bayview OS already supports:

- Projects;
- Work Items;
- Decisions;
- Evidence;
- Knowledge;
- Operating Records;
- Independent approvals;
- Project status;
- priorities;
- blockers;
- relationships;
- attachments or source references;
- audit history;
- APIs;
- database row-level security;
- user-facing project pages.

Produce an evidence-backed capability matrix:

| Required LMIO memory capability | Existing Bayview OS capability | Reuse / extend / missing | Evidence |
|---|---|---|---|

### 4.3 Gap analysis

Classify each requirement:

- reuse unchanged;
- configure;
- extend minimally;
- create new;
- defer.

Do not build anything until the implementation map is complete.

---

## 5. Required First Deliverable: Implementation Map

Create and save:

```text
docs/projects/lmio/LMIO_BAYVIEW_OS_IMPLEMENTATION_MAP.md
```

It must include:

1. verified current repository status;
2. relevant existing modules;
3. current database entities;
4. existing APIs;
5. current UI support;
6. gaps;
7. exact files expected to change;
8. proposed migrations;
9. proposed new routes;
10. test plan;
11. risk and rollback plan;
12. phased delivery;
13. cost dependencies;
14. decisions requiring Leon;
15. explicit confirmation that no live trading will be added.

Register this implementation map as a Knowledge/Evidence record in Bayview OS.

---

## 6. Create LMIO as a Formal Bayview OS Project

Create one canonical project record.

### 6.1 Project identity

Use:

```text
Name: Leon Market Intelligence OS
Code: LMIO
Owner: Leon
Status: Active — Planning / Build
Priority: High
Domain: Investment Intelligence / AI Systems
Default language: Chinese
Market: United States Equities
```

### 6.2 Project objective

Use this concise objective:

```text
Build a persistent AI-assisted market intelligence operating system that
scans United States equities, identifies evidence-backed opportunities,
evaluates company quality and intrinsic value, supports news-driven conditional
trade planning, delivers priority alerts through Telegram, and continuously
measures the outcome of every signal.
```

### 6.3 Project boundaries

Record:

- V1 has no live trading;
- V1 has no autonomous order execution;
- Telegram is an alert channel;
- Dashboard is the full evidence surface;
- Bayview OS is the memory and governance layer;
- LMIO is the product/runtime layer.

### 6.4 Project relationships

Link LMIO to:

- Bayview OS;
- any existing IBKR trading-engine project;
- any existing market-intelligence project;
- the governing Master Specification;
- this Codex Start Instruction.

Do not merge LMIO into the existing trading engine. Keep a clear boundary:

```text
LMIO discovers, researches, values, ranks and plans.

The trading engine, if connected later, owns broker execution and deterministic
portfolio risk.
```

---

## 7. Bayview OS Memory Model for LMIO

Reuse the existing Bayview OS model wherever possible.

### 7.1 Project record

Stores:

- identity;
- objective;
- status;
- priority;
- scope;
- owner;
- current phase;
- current health;
- next milestone.

### 7.2 Work items

Every material piece of work must be a work item with:

- stable ID;
- title;
- description;
- phase;
- status;
- priority;
- owner/agent;
- dependencies;
- acceptance criteria;
- evidence links;
- blocker;
- next action;
- created and updated timestamps.

### 7.3 Decisions

Every material decision must record:

- question;
- decision;
- date;
- decision maker;
- context;
- alternatives;
- reason;
- consequences;
- affected work;
- review trigger.

Do not record every minor code choice as a product decision. Use ADRs for architectural choices.

### 7.4 Evidence

Evidence must include:

- test output;
- screenshots where relevant;
- API verification;
- database assertions;
- migration verification;
- source citations;
- deployment verification;
- sample reports;
- Telegram delivery confirmation;
- valuation-reproduction output.

Claims such as “completed”, “working”, “deployed” or “verified” require evidence.

### 7.5 Knowledge

Knowledge records must include:

- Master Specification;
- this Start Instruction;
- architecture;
- data-provider research;
- valuation methodology;
- strategy definitions;
- operating manual;
- deployment guide;
- troubleshooting guide;
- handover summaries.

### 7.6 Operating records

Keep operating records concise and focused on:

- discussion conclusion;
- direction;
- what changed;
- current blocker;
- next action.

Do not bury project memory in long conversational logs.

---

## 8. Required LMIO Phases in Bayview OS

Create the following phase records and work-item groups.

### LMIO-000 — Project Registration and Discovery

Deliver:

- canonical Bayview OS project;
- source-document records;
- repository discovery;
- capability matrix;
- implementation map;
- initial risk register.

### LMIO-001 — Foundation

Deliver:

- LMIO service/repository decision;
- local development environment;
- configuration validation;
- database namespace/schema;
- provider interfaces;
- health checks;
- audit logging;
- test framework.

### LMIO-002 — Investable Universe

Deliver:

- United States equity universe;
- exclusions;
- liquidity filters;
- average dollar volume;
- market/sector classification;
- reproducible daily universe build.

### LMIO-003 — Screening Engine

Deliver:

- Finviz-style filters;
- Quality Growth Momentum;
- Earnings Revision Momentum where data exists;
- Institutional Accumulation;
- Insider Value;
- strategy-specific results;
- no mixed unexplained ranking.

### LMIO-004 — News and SEC Intelligence

Deliver:

- news-provider adapters;
- SEC filing ingestion;
- source tiers;
- event classification;
- deduplication;
- market-moving thresholds;
- no-news-trading safety boundary.

### LMIO-005 — Intrinsic Value

Deliver:

- Strict FCF Value;
- Normalised Owner Earnings Value;
- Multi-Model Fair Value;
- pessimistic/base/optimistic cases;
- sensitivity;
- confidence;
- fully diluted shares;
- assumption audit;
- META acceptance case.

### LMIO-006 — Four-Dimension Scoring

Deliver:

- Company Quality Score;
- Valuation Score;
- Opportunity Score;
- Timing Score;
- strategy-specific weighting;
- full score explanation;
- score-version history.

### LMIO-007 — Research Agent

Deliver:

- structured research schema;
- filing/transcript workflow;
- Kimi adapter or documented manual integration;
- OpenAI synthesis adapter;
- bull/bear evidence;
- invalidation and next confirmation.

### LMIO-008 — Trade with News

Deliver:

- Surprise Engine;
- affected-symbol mapping;
- reaction windows;
- price/volume verification;
- conditional trade-plan creation;
- explicit no-live-order enforcement.

### LMIO-009 — Telegram

Deliver:

- Chinese pre-market brief;
- P0/P1 alerts;
- delivery status;
- deduplication;
- mute/watch actions where supported;
- no secret exposure.

### LMIO-010 — Dashboard

Deliver:

- Command Centre;
- Top 10;
- Top 3;
- Strategy Screener;
- News Trading;
- Institutional/Insider;
- Intrinsic Value;
- Watchlists;
- Reports;
- System Health.

### LMIO-011 — Outcome Tracking

Deliver:

- signal snapshots;
- 1-hour, close, 1-day, 5-day and 20-day outcomes;
- MFE/MAE;
- benchmark comparison;
- strategy and regime performance;
- Leon feedback.

### LMIO-012 — Production Readiness

Deliver:

- migrations;
- security review;
- provider readiness;
- monitoring;
- backup/recovery plan;
- deployment;
- operating manual;
- final V1 acceptance report.

### Deferred phases

Create but mark deferred:

- LMIO-020 Unusual Options;
- LMIO-021 Social/X Intelligence;
- LMIO-030 IBKR Paper Trading;
- LMIO-040 Strategy Calibration;
- LMIO-050 Live Trading Review.

Do not implement deferred phases without a formal phase decision.

---

## 9. How LMIO Should Integrate Technically With Bayview OS

Choose the least-coupled architecture that preserves one source of project memory.

Preferred model:

```text
Bayview OS
  - project/work/decision/evidence/knowledge records
  - governance and human-readable status

LMIO
  - market data
  - financial data
  - news
  - screens
  - valuation
  - signal scoring
  - conditional trade plans
  - outcome tracking

Integration
  - stable project ID
  - stable work-item IDs
  - evidence references
  - status-sync API or service
  - scheduled operating summaries
```

Do not place high-volume tick, news or options data inside Bayview OS project-memory tables.

Bayview OS should store:

- the work being done;
- the governing decision;
- the evidence that it works;
- the summary outcome;
- the link/reference to detailed LMIO data.

LMIO should store:

- high-volume market and company data;
- calculation inputs and outputs;
- event and signal histories;
- detailed operational records.

This boundary is mandatory to prevent Bayview OS becoming a market-data warehouse.

---

## 10. Ongoing Memory Writeback Rules

At the end of every meaningful Codex work session:

1. update the relevant work-item status;
2. write a concise operating record;
3. attach or reference evidence;
4. record any new decision;
5. record blockers;
6. set the next action;
7. update project health if materially changed;
8. update the handover summary.

The handover must answer:

```text
Current phase:
Last completed work:
Evidence:
Current blocker:
Next exact task:
Decisions pending:
Files/commits/PRs:
Deployment status:
```

No future agent should need the original chat to continue.

---

## 11. Required Bayview OS Views

Reuse existing views where possible. Extend only when necessary.

LMIO project page should make visible:

- project objective;
- locked boundaries;
- current phase;
- progress by LMIO phase;
- active work;
- blocked work;
- recent decisions;
- recent evidence;
- source documents;
- latest operating record;
- next action;
- system/deployment health;
- cost approvals pending.

Do not create a second generic project-management UI inside LMIO.

---

## 12. Supabase and Persistence

Leon has an existing Supabase Free account available.

Before asking Leon for account access:

1. inspect current repository configuration;
2. determine what is already connected;
3. identify the exact missing credential or action;
4. explain why it is required;
5. request only the minimum login/authorisation step.

Do not ask Leon to paste secrets into source files or chat.

Use:

- migrations;
- row-level security;
- least privilege;
- development/test separation where possible;
- seed data without secrets;
- reproducible schema verification.

Do not incur paid Supabase cost without Leon's approval.

---

## 13. Provider and Cost Discipline

Start with free or already available sources where technically adequate:

- SEC EDGAR;
- existing IBKR-accessible data;
- Supabase Free;
- Telegram;
- one selected fundamentals/news provider;
- selective AI calls.

For every paid service, create a Bayview OS decision/work item containing:

- data need;
- provider;
- exact feature;
- monthly and annual cost;
- trial availability;
- free or cheaper alternative;
- expected improvement;
- consequence of deferring;
- Leon approval status.

Do not purchase or activate:

- professional real-time news;
- unusual-options feed;
- estimate-revision feed;
- X API;
- paid hosting;
- premium market data;

without Leon's approval.

---

## 14. Git and Delivery Rules

Before editing:

- confirm repository;
- confirm branch;
- inspect working tree;
- identify unrelated user changes;
- read repository instructions.

During implementation:

- use small, reviewable commits;
- keep migrations and tests with the feature;
- reference LMIO work-item IDs in commits where practical;
- do not mix unrelated refactoring;
- keep source documents versioned;
- update Bayview OS memory with commit/PR evidence.

Do not push, merge or deploy beyond the authority granted by the active user request and repository workflow.

If the user has asked Codex to finish the system, continue autonomously through safe implementation and verification. Involve Leon only when:

- login or authorisation is required;
- payment is required;
- a material product decision is required;
- a protected production action requires approval;
- a risk boundary would change.

---

## 15. Initial Acceptance Criteria

This start instruction is fulfilled when:

1. The actual Bayview OS state has been inspected.
2. LMIO exists as one canonical Bayview OS project.
3. The Master Specification and this instruction are registered as governing knowledge.
4. LMIO-000 through LMIO-012 work groups exist.
5. Deferred phases exist but are not active.
6. Locked product boundaries are recorded.
7. The capability matrix is complete.
8. The implementation map is complete.
9. The first executable work item is ready.
10. Bayview OS shows the current phase, next action and blockers.
11. A future Codex session can continue without relying on this conversation.
12. No live-trading feature has been introduced.
13. No paid service has been activated.

---

## 16. First Execution Sequence

Execute in this order:

```text
1. Inspect repository and instructions.
2. Verify current AEO/Bayview OS implementation state.
3. Run existing safe tests.
4. Build capability matrix.
5. Create implementation map.
6. Register LMIO project.
7. Register governing documents.
8. Create phase/work-item structure.
9. Record locked decisions and risks.
10. Select the first LMIO foundation work item.
11. Implement only after the map and records exist.
12. Update Bayview OS memory before ending the session.
```

---

## 17. Required First Response to Leon

After discovery and registration, report concisely:

```text
LMIO has been registered in Bayview OS.

Verified Bayview OS state:
Reused capabilities:
Required extensions:
First active phase:
First work item:
Current blockers:
Login/payment required now:
Next action:
```

Do not give Leon a generic plan after being instructed to execute. Perform the safe work first, then report evidence.

---

## 18. Final Instruction

Take ownership of the build while preserving the product and safety boundaries.

The project is successful only if:

- LMIO becomes useful;
- its calculations are reproducible;
- its evidence is auditable;
- its alerts are selective;
- its progress survives across conversations;
- its next action is always visible;
- Bayview OS remains the durable memory of the project.

