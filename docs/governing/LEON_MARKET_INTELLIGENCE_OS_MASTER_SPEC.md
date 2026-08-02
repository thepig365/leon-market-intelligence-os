# Leon Market Intelligence OS

## Master Product and Technical Specification

**Document status:** V1.0 — Source of Truth  
**Date:** 30 July 2026  
**Owner:** Leon  
**Working name:** LMIO  
**Primary market:** United States equities  
**Default output language:** Chinese  

---

## 1. Executive Summary

Leon Market Intelligence OS is an AI-assisted market intelligence, stock-selection, valuation, news-trading support, and research operating system.

Its purpose is not to generate a large volume of generic stock tips. Its purpose is to reduce the United States equity market from thousands of securities to a small number of evidence-backed opportunities, explain why they matter, calculate what they may be worth, determine whether the timing is acceptable, and track whether the original thesis was correct.

The intended daily funnel is:

```text
Approximately 11,000 listed securities
→ approximately 1,000 investable securities
→ approximately 100 abnormal candidates
→ approximately 20 researched candidates
→ Top 10 watchlist
→ Top 3 priority opportunities
→ 0–1 qualified conditional trade plans
```

LMIO must answer five questions for every serious candidate:

1. What has changed?
2. Why does it matter?
3. Is the change supported by company fundamentals, institutional behaviour, price, volume, options, or industry evidence?
4. What is the reasonable intrinsic value range?
5. Is the present price and market structure suitable for action now?

The first release is an intelligence and decision-support system. It is not a live autonomous trading system.

---

## 2. Product Principles

### 2.1 Evidence before opinion

Every formal signal must preserve:

- source;
- publication or filing time;
- market-data timestamp;
- raw input;
- transformation and scoring logic;
- model and prompt version;
- assumptions;
- invalidation conditions.

AI commentary without supporting evidence must never be treated as a formal signal.

### 2.2 Separate company quality, value, opportunity and timing

A good company may be overpriced.  
A cheap company may be deteriorating.  
A strong catalyst may already be priced in.  
A valid long-term opportunity may have poor short-term timing.

LMIO must therefore maintain four independent scores:

1. Company Quality Score;
2. Valuation Score;
3. Opportunity Score;
4. Timing Score.

The system must not hide these distinctions inside one unexplained composite number.

### 2.3 News informs; price verifies

News can:

- alert;
- rank;
- explain;
- add or remove a symbol from a watchlist;
- raise risk;
- block a proposed trade.

News alone cannot trigger a live order.

### 2.4 AI interprets; deterministic code calculates

Language models may:

- summarise filings and earnings calls;
- classify news;
- identify relationships;
- produce counterarguments;
- explain financial or market implications.

Deterministic services must:

- calculate scores;
- calculate intrinsic value;
- calculate price and volume indicators;
- enforce thresholds;
- enforce risk limits;
- deduplicate events;
- manage state;
- produce auditable records.

### 2.5 No false precision

Intrinsic value must be a range, not a magical exact number.  
News significance must display evidence and uncertainty.  
Probabilities must not be invented where there is no calibrated model.

### 2.6 Quiet by default

Telegram is for short and important alerts only. Low-quality or repetitive events must be stored without disturbing Leon.

---

## 3. Scope

### 3.1 V1 scope

V1 includes:

- United States equity universe;
- investability and liquidity filters;
- multi-strategy stock screening;
- earnings and estimate-revision screening;
- basic institutional and insider analysis;
- SEC filing monitoring;
- market-moving news detection;
- Trade with News decision support;
- three-method intrinsic-value analysis;
- opportunity scoring;
- Chinese pre-market brief;
- Telegram alerts;
- web dashboard;
- watchlists;
- evidence storage;
- signal performance tracking;
- system health monitoring.

### 3.2 Later scope

Later phases may include:

- unusual options-flow provider;
- X data;
- deeper social-sentiment monitoring;
- real-time VWAP and opening-range confirmation;
- IBKR paper trading;
- bracket-order simulation;
- portfolio-level risk;
- strategy calibration;
- limited live trading after formal approval.

### 3.3 Explicit non-goals for V1

V1 must not:

- execute live trades;
- switch silently from paper to live trading;
- buy or sell based only on a headline;
- trade based only on X, Reddit or Stocktwits;
- claim guaranteed returns;
- treat analyst price targets as intrinsic value;
- treat every large call option transaction as bullish;
- treat high short interest as an automatic short squeeze;
- scrape or use data in breach of provider terms;
- expose API keys, tokens or account credentials.

---

## 4. User Experience and Final Daily Result

The principal experience is a command centre that gives Leon:

### 4.1 Market regime

```text
Market regime: Risk-On / Risk-Off / High Volatility /
Low Volatility / Range / Macro Shock
```

It must include:

- SPY, QQQ and IWM direction;
- VIX and volatility structure;
- market breadth;
- leading and lagging sectors;
- United States 2-year and 10-year yields;
- DXY;
- USD/JPY and JPY-strength risk;
- oil and gold;
- key scheduled macro events.

The system must preserve the transmission-risk hypothesis:

```text
Rapid JPY strengthening
→ carry-trade unwinding
→ pressure on global risk assets
```

### 4.2 Daily funnel

```text
Universe checked:
Investable:
Abnormal candidates:
Researched:
Watchlist:
Priority opportunities:
Qualified trade plans:
```

### 4.3 Top 10 watchlist

Every entry must show:

- ticker and company;
- primary strategy;
- central catalyst;
- four independent scores;
- market price;
- intrinsic-value range;
- next confirmation needed;
- invalidation condition;
- intended time horizon.

### 4.4 Top 3 priority opportunities

Each priority opportunity receives a full decision card:

```text
Ticker:
Strategy:
What changed:
Why it matters:

Company Quality:
Valuation:
Opportunity:
Timing:

Market price:
Strict FCF value:
Normalised Owner Earnings value:
Multi-model fair value:
Base safety margin:
Valuation confidence:

Supporting evidence:
Contrary evidence:
Key risks:

Confirmation condition:
Entry zone:
Invalidation:
Stop reference:
Target reference:
Risk/reward:
Current status:
```

### 4.5 No forced recommendation

It is valid and expected for the daily result to contain:

```text
No qualified trade plan today.
```

The system must not lower standards merely to produce an idea every day.

---

## 5. High-Level Architecture

```text
External Data Providers
        ↓
Provider Adapters
        ↓
Normalisation / Entity Resolution / Deduplication
        ↓
Investable Universe
        ↓
Screening and Event Detection
        ↓
Research and Evidence Graph
        ↓
Valuation + Four-Dimension Scoring
        ↓
Conditional Trade Plan + Risk Gate
        ↓
Telegram / Dashboard / Reports
        ↓
Outcome Tracking and Strategy Evaluation
```

### 5.1 Principal components

| Component | Responsibility |
|---|---|
| Python services | Calculations, filtering, valuation, scoring and risk rules |
| FastAPI | Service API and orchestration endpoints |
| PostgreSQL/Supabase | Persistent structured data |
| Hermes | 24/7 scheduling, task orchestration, retries and monitoring |
| Kimi | Long-document, earnings-call and bulk research assistant |
| OpenAI | Higher-level synthesis, structured analysis and review |
| Codex | System implementation, tests, deployment and maintenance |
| n8n | Simple integrations and notification workflows only |
| Next.js/TypeScript | Dashboard |
| Telegram Bot | Priority alert and control channel |
| IBKR | Market/broker data and later paper trading |

### 5.2 Provider abstraction

No core service may depend directly on one provider-specific response format.

Each data category must use an adapter interface:

```text
NewsProvider
MarketDataProvider
FundamentalsProvider
EstimateRevisionProvider
InstitutionalProvider
InsiderProvider
OptionsFlowProvider
SocialProvider
BrokerProvider
```

If a provider is missing or fails:

- mark the provider unhealthy;
- preserve the error;
- skip safely where possible;
- lower data confidence;
- do not invent replacement values;
- do not block unrelated modules unnecessarily.

---

## 6. Data Requirements

### 6.1 Market data

- daily OHLCV;
- intraday OHLCV;
- pre-market and after-hours price;
- current and average volume;
- average dollar volume;
- relative volume;
- VWAP;
- SMA20, SMA50 and SMA200;
- 20-day, 50-day and 52-week highs/lows;
- ATR;
- realised volatility;
- gap;
- sector and industry ETF mapping.

### 6.2 Fundamental data

- revenue;
- EPS;
- operating income;
- operating margin;
- gross margin;
- net income;
- operating cash flow;
- capital expenditure;
- free cash flow;
- cash and marketable securities;
- debt;
- diluted shares;
- stock-based compensation;
- share issuance and repurchases;
- ROA, ROE and calculated ROIC;
- working-capital changes;
- consensus revenue and EPS;
- forward estimates;
- estimate revisions over 7, 30 and 90 days.

### 6.3 Ownership data

- Form 13F;
- Schedule 13D and amendments;
- Schedule 13G and amendments;
- Forms 3, 4 and 5;
- institutional ownership;
- institutional transactions;
- active versus passive manager classification;
- new, increased, reduced and exited positions;
- short interest;
- days to cover;
- borrow fee where available.

### 6.4 News and events

- company investor relations;
- SEC filings;
- earnings releases;
- earnings-call transcripts;
- guidance;
- mergers and acquisitions;
- buybacks, offerings and convertible notes;
- CEO/CFO changes;
- FDA;
- DOJ, FTC, SEC and court events;
- cyber incidents;
- customer or contract events;
- analyst estimate changes;
- macroeconomic data;
- central-bank events;
- sanctions, tariffs and export restrictions.

### 6.5 Options data

- option volume;
- open interest;
- implied volatility;
- premium;
- bid/ask position;
- expiry;
- strike;
- underlying price;
- sweep/block classification where available;
- expected move;
- spread and hedge likelihood.

### 6.6 Social data

- mention count;
- mention acceleration;
- unique-account count;
- account quality;
- bot likelihood;
- sentiment;
- source links;
- topic clustering;
- first-seen time.

Social data is an investigation trigger, not independent trading authority.

---

## 7. Investable Universe

### 7.1 Default discovery universe

- NASDAQ, NYSE and AMEX;
- common equity;
- price at least US$5;
- market capitalisation at least US$500M;
- 20-day average dollar volume at least US$20M;
- sufficient fundamental and price data.

### 7.2 Formal trade-candidate universe

- price at least US$10;
- market capitalisation at least US$1B;
- average dollar volume at least US$50M;
- acceptable spread;
- no active halt;
- reliable real-time data;
- options strategies require acceptable option liquidity.

### 7.3 Exclusions

- OTC;
- most shell companies and SPACs;
- frequent reverse-split securities;
- securities with severe data-quality problems;
- obvious manipulation-risk microcaps;
- securities failing configured liquidity thresholds.

Exceptions for special situations must be explicit and labelled high risk.

---

## 8. Finviz Role and Initial Screening

Finviz is a reference and manual validation layer, not LMIO's final decision engine.

### 8.1 Most useful Finviz-style filters

- EPS Growth Q/Q;
- Sales Growth Q/Q;
- EPS Growth Next Year;
- ROE;
- Operating Margin;
- Debt/Equity;
- price above SMA50;
- price above SMA200;
- SMA50 above SMA200;
- distance from 52-week high;
- quarter and half-year performance;
- relative volume;
- institutional transactions;
- insider transactions;
- price/free cash flow.

### 8.2 Lower-reliability filters

The following must not be primary decision factors:

- analyst recommendation;
- analyst target price;
- PEG alone;
- P/B outside appropriate industries;
- RSI oversold alone;
- automated chart pattern alone;
- unusual volume without market-cap and liquidity filters.

### 8.3 Default Quality Growth Momentum screen

```text
Country: USA
Market Cap: over US$2B
Price: over US$10
Average Volume: over 500K
Optionable: yes where relevant

EPS Growth Q/Q: over 15%
Sales Growth Q/Q: over 10%
EPS Growth Next Year: over 10%
ROE: over 15%
Operating Margin: positive
Debt/Equity: under 1
Institutional Transactions: positive

Price above SMA50
Price above SMA200
SMA50 above SMA200
Performance Quarter positive
Price within 20% of 52-week high
```

LMIO must calculate average dollar volume and sector-relative metrics itself.

---

## 9. Stock-Selection Strategies

Strategies must run independently. Their outputs may overlap, but each candidate must retain its originating strategy and applicable time horizon.

### 9.1 Quality Growth Momentum

Purpose: identify profitable, liquid market leaders with fundamental and price confirmation.

Core evidence:

- EPS growth;
- sales growth;
- future EPS growth;
- profitability;
- manageable debt;
- positive relative strength;
- constructive price trend;
- institutional participation.

### 9.2 Earnings Revision Momentum

Purpose: identify changes in future market expectations.

Required calculations:

```text
Revision Breadth =
(Upward Revisions - Downward Revisions) / Total Revisions

EPS Revision =
(New Consensus - Old Consensus) / abs(Old Consensus)
```

Inputs:

- 7-day EPS revision;
- 30-day EPS revision;
- 90-day EPS revision;
- revenue revisions;
- number of upward and downward revisions;
- company guidance;
- recent earnings surprise;
- price and sector confirmation.

This is a priority V1 strategy.

### 9.3 Institutional Accumulation

Do not use institutional ownership percentage alone.

Track:

- number of new institutional positions;
- number of increased positions;
- number of reduced positions;
- number of exits;
- net share change;
- consecutive-quarter accumulation;
- active versus passive institutions;
- concentration among high-quality managers;
- institution's historical sector skill;
- relationship between accumulation and estimate revisions.

Form 13F is a delayed quarterly confirmation signal, not a real-time entry signal.

### 9.4 Activist Catalyst

Schedule 13D events receive separate treatment.

Extract:

- investor identity;
- ownership percentage;
- estimated cost;
- purpose of transaction;
- board-seat request;
- sale, break-up, capital-allocation or governance proposal;
- subsequent amendments;
- investor's prior outcomes.

### 9.5 Insider Value

Prioritise:

- open-market cash purchases by CEO/CFO/directors;
- cluster buying;
- economically meaningful purchase size;
- purchases near present price;
- buying after a decline without fundamental collapse.

Exclude or separately classify:

- grants;
- RSU vesting;
- tax withholding;
- option exercise followed by sale;
- 10b5-1 selling;
- symbolic purchases.

### 9.6 Quality at a Reasonable Price

Require:

- high or improving ROIC;
- cash-flow quality;
- controlled debt;
- manageable dilution;
- non-declining estimates;
- positive safety margin;
- stabilising or improving price structure.

### 9.7 Earnings Breakout / PEAD

Look for:

- EPS and revenue surprise;
- guidance surprise;
- improving operating metrics;
- subsequent analyst revisions;
- high relative volume;
- close near event-day high;
- gap retention;
- industry confirmation.

### 9.8 News-Driven Trade

Defined in Section 12.

### 9.9 Unusual Options Confirmation

Calculate:

- Volume/Open Interest;
- volume/history ratio;
- total premium;
- bid/ask position;
- repeated direction;
- strike distance;
- time to expiry;
- IV change;
- earnings proximity;
- spread or hedge likelihood.

Options flow is a confirmation factor and must not independently create a high-priority trade.

### 9.10 Oversold Structural Reversal

RSI alone is insufficient.

State model:

```text
Potential divergence
→ preliminary stabilisation
→ divergence candidate
→ structural confirmation
→ confirmed reversal
→ divergence failure
```

Required confirmation may include:

- no new low during verification window;
- reduced selling pressure;
- break of short-term downtrend;
- recovery of VWAP or key structure;
- creation or recovery of a lower-timeframe consolidation zone;
- fundamental or valuation support.

### 9.11 Short Squeeze

Require a combination of:

- high short float;
- high days to cover;
- rising borrow cost;
- identifiable catalyst;
- price breakout;
- volume expansion;
- option/Gamma confirmation.

High short interest alone is not bullish.

### 9.12 Theme and Social Acceleration

Require:

- rapid increase in mentions;
- multiple independent credible accounts;
- a real underlying event;
- related-stock or industry confirmation;
- price or volume confirmation.

Bot amplification, recycled news and single-influencer promotion must reduce confidence.

---

## 10. Four-Dimension Scoring

### 10.1 Company Quality Score

Indicative inputs:

- ROIC and spread over cost of capital;
- gross and operating margins;
- FCF conversion;
- earnings stability;
- revenue stability;
- leverage;
- interest coverage;
- share dilution;
- SBC intensity;
- capital allocation;
- governance and accounting quality.

### 10.2 Valuation Score

Indicative inputs:

- Strict FCF value;
- Normalised Owner Earnings value;
- Multi-Model Fair Value;
- safety margin;
- valuation confidence;
- historical valuation;
- peer valuation;
- FCF yield;
- earnings yield;
- sensitivity.

### 10.3 Opportunity Score

Indicative inputs:

- estimate revisions;
- earnings surprise;
- guidance;
- event significance;
- institutional accumulation;
- insider buying;
- options confirmation;
- sector strength;
- social acceleration;
- contrary evidence.

### 10.4 Timing Score

Indicative inputs:

- price structure;
- relative strength;
- VWAP;
- relative volume;
- gap retention;
- distance from support/resistance;
- distance from moving averages;
- overextension;
- market regime;
- scheduled event risk;
- risk/reward.

### 10.5 Strategy-specific weighting

Long-term strategy example:

| Dimension | Weight |
|---|---:|
| Company Quality | 30% |
| Valuation | 30% |
| Opportunity | 20% |
| Timing | 20% |

News-trading example:

| Input | Weight |
|---|---:|
| Catalyst and surprise | 30% |
| Price and volume | 30% |
| Options confirmation | 20% |
| Market regime | 15% |
| Valuation context | 5% |

The system must not compare long-term and news-trading candidates using one identical total score.

---

## 11. Intrinsic Value Engine

### 11.1 Required outputs

Every valuation must show:

- pessimistic value;
- base value;
- optimistic value;
- safety margin;
- valuation confidence;
- sensitivity table;
- model applicability;
- key assumptions;
- calculation date;
- source data;
- model version.

### 11.2 Three-model framework

LMIO must show three distinct valuation perspectives:

#### A. Strict FCF Value

```text
Operating Cash Flow
- Purchases of Property and Equipment
- Finance Lease Principal
= Reported Free Cash Flow
```

This shows the effect of actual current cash expenditure.

#### B. Normalised Owner Earnings Value

This model separates:

- maintenance CapEx;
- growth CapEx;
- temporary working-capital effects;
- non-recurring costs;
- recurring SBC and dilution;
- sustainable operating economics.

The maintenance/growth split must be visible and confidence-scored.

#### C. Multi-Model Fair Value

This combines applicable models:

- FCFF/FCFE DCF;
- revenue-exit DCF;
- EBITDA-exit DCF;
- earnings-power value;
- P/E;
- EV/EBITDA;
- EV/Revenue;
- P/FCF;
- DDM where appropriate;
- industry-specific models.

Do not apply models that are inappropriate for the company type.

### 11.3 Company-type routing

| Company type | Preferred models |
|---|---|
| Stable profitable company | FCFF/FCFE DCF |
| High-growth technology | Revenue-to-margin DCF plus multiples |
| Bank/insurance | Residual income, DDM and P/B |
| REIT | AFFO/FFO and NAV |
| Cyclical | Normalised earnings and EV/EBITDA |
| Unprofitable | Revenue scenarios with low confidence |
| Resource company | NAV and commodity-price scenarios |
| Mature dividend payer | DDM and FCFE |
| Special situation | Deal value and break value |

### 11.4 DCF equations

```text
FCFF = EBIT × (1 - Tax Rate)
       + Depreciation and Amortisation
       - Capital Expenditure
       - Change in Net Working Capital
```

```text
Enterprise Value =
Σ FCFF(t) / (1 + WACC)^t
+ Terminal Value / (1 + WACC)^n
```

```text
Terminal Value =
FCFF(n+1) / (WACC - Terminal Growth)
```

```text
Equity Value =
Enterprise Value
+ Cash
- Debt
- Minority Interest
```

```text
Intrinsic Value Per Share =
Equity Value / Fully Diluted Shares
```

### 11.5 Hard valuation rules

- WACC must exceed terminal growth;
- fully diluted shares must be used;
- restricted cash must not automatically equal usable cash;
- material lease and contractual obligations must be considered;
- SBC must be visible;
- one-time tax effects must be normalised;
- terminal value share of enterprise value must be reported;
- stale data must reduce confidence;
- AI cannot silently change assumptions;
- results must be reproducible.

### 11.6 Safety margin

```text
Margin of Safety =
(Intrinsic Value - Market Price) / Intrinsic Value
```

Indicative labels:

| Safety margin | Label |
|---|---|
| above 30% | Substantial |
| 20–30% | Attractive |
| 10–20% | Moderately undervalued |
| within ±10% | Near fair value |
| below -10% | Moderately overvalued |
| below -30% | Substantially overvalued |

Thresholds must be adjusted for quality and valuation confidence.

### 11.7 Meta validation case

META must be included as an initial valuation acceptance test because its large AI CapEx demonstrates why one model is insufficient.

As of 30 July 2026, the model must be capable of showing:

- strong revenue growth;
- falling reported FCF due to AI infrastructure CapEx;
- lower operating margin;
- maintenance versus growth CapEx uncertainty;
- one-time tax effects;
- higher debt and infrastructure commitments;
- divergence between Strict FCF, Normalised Owner Earnings and multi-model fair value.

The system should not force the three values to agree.

---

## 12. Trade with News

### 12.1 Definition

Trade with News converts a verified event into a conditional trade plan only after market reaction is observed.

```text
News
→ verify
→ classify
→ measure surprise
→ map affected securities
→ observe reaction
→ confirm with price/volume/options/industry
→ create conditional plan
→ risk review
→ paper monitoring
```

### 12.2 Source tiers

#### Tier 1

- SEC;
- company investor relations;
- earnings release;
- exchange;
- Fed and government;
- court and regulator;
- official company announcement.

#### Tier 2

- Reuters;
- Bloomberg;
- Dow Jones;
- Financial Times;
- CNBC;
- Benzinga;
- IBKR News.

#### Tier 3

- X;
- Reddit;
- Stocktwits;
- YouTube;
- Discord;
- unverified media.

Tier 3 creates an investigation task only. It cannot independently create a formal trade plan.

### 12.3 Event types

- earnings surprise;
- guidance change;
- merger/acquisition;
- FDA decision;
- SEC/DOJ/FTC action;
- offering, convertible or buyback;
- CEO/CFO departure;
- major contract or customer loss;
- product event;
- cyber incident;
- export restriction or tariff;
- macro data;
- central-bank decision;
- geopolitical shock.

### 12.4 News Impact Score

Indicative components:

| Factor | Points |
|---|---:|
| Source credibility | 0–15 |
| Novelty | 0–15 |
| Revenue/profit impact | 0–20 |
| Difference from expectation | 0–15 |
| Price reaction | 0–15 |
| Volume confirmation | 0–10 |
| Options confirmation | 0–10 |
| Risk deduction | 0 to -30 |

Priority:

- P0: 85–100;
- P1: 70–84;
- watch: 55–69;
- store silently: below 55.

P0 means immediate analysis, not automatic purchase.

### 12.5 Surprise Engine

```text
EPS Surprise =
(Actual EPS - Consensus EPS) / abs(Consensus EPS)
```

```text
Revenue Surprise =
(Actual Revenue - Consensus Revenue) / Consensus Revenue
```

Also compare:

- company guidance versus consensus;
- whisper estimate where lawfully available;
- option-implied expected move;
- actual price move;
- prior market positioning.

### 12.6 Reaction windows

| Window | Purpose |
|---|---|
| T0 | verify and classify |
| T+1 minute | initial reaction |
| T+5 minutes | continuation or reversal |
| T+15 minutes | VWAP/opening structure |
| T+30–60 minutes | trade confirmation |
| Close | event-day assessment |
| 1–5 days | drift or failure |

### 12.7 Supported news strategies

- positive earnings continuation;
- negative guidance breakdown;
- merger arbitrage;
- good-news reaction failure;
- bad-news reaction failure;
- secondary beneficiary;
- macro transmission;
- post-earnings drift.

### 12.8 Required conditional plan

```text
Ticker:
Event:
Sources:
Direction hypothesis:
News Impact Score:
Market reaction:
Expected move:

Confirmation:
Entry zone:
Invalidation:
Stop reference:
Target reference:
Risk/reward:
Current status:
```

---

## 13. Market Regime Engine

### 13.1 Inputs

- SPY/QQQ/IWM trend;
- breadth;
- VIX;
- sector leadership;
- Treasury yields;
- DXY;
- USD/JPY;
- oil;
- gold;
- major scheduled events.

### 13.2 Outputs

- regime classification;
- confidence;
- supporting evidence;
- contrary evidence;
- preferred strategies;
- suppressed strategies;
- risk multiplier;
- blocked symbols or sectors;
- manual-review requirement.

### 13.3 Example policy

In Risk-On:

- increase weight for quality momentum;
- earnings continuation;
- confirmed call flow.

In Risk-Off:

- reduce momentum chase;
- prioritise defence and capital preservation;
- elevate negative guidance and put confirmation;
- demand higher safety margin.

In Macro Shock:

- suppress ordinary low-priority signals;
- block automatic paper entries until stability criteria pass;
- prioritise risk reporting.

---

## 14. Research Agent

Every Top 20 candidate receives a structured research package.

### 14.1 Required output

1. Company and business model;
2. What changed;
3. Primary sources;
4. Financial and operational impact;
5. Estimate revisions;
6. Institutional and insider behaviour;
7. Price/volume/sector confirmation;
8. Options evidence;
9. Intrinsic-value implications;
10. strongest bull case;
11. strongest bear case;
12. disconfirming evidence;
13. key risks;
14. next confirmation;
15. invalidation.

### 14.2 Kimi role

Kimi may:

- read long filings;
- compare earnings calls;
- summarise transcripts;
- cluster social discussion;
- produce first-pass research.

Kimi must not:

- own the scheduler;
- calculate final valuation without deterministic verification;
- set risk limits;
- execute orders;
- override source-quality rules.

---

## 15. Candidate and Trade State Machines

### 15.1 Candidate state

```text
DISCOVERED
→ FILTERED
→ RESEARCHING
→ WATCHING
→ CONFIRMED
→ REJECTED
→ EXPIRED
```

### 15.2 Trade-plan state

```text
DRAFT
→ WAITING_CONFIRMATION
→ PAPER_READY
→ PAPER_OPEN
→ INVALIDATED
→ CLOSED
→ REVIEWED
```

Every transition must record:

- timestamp;
- actor;
- evidence;
- previous state;
- new state;
- reason.

---

## 16. Telegram

### 16.1 Fixed reports

- one hour before United States market open: Chinese pre-market brief;
- 15–30 minutes after open: confirmation update;
- after close: signal review;
- weekend: strategy performance report.

The existing 08:30 America/New_York pre-market workflow may be retained where operationally appropriate, with correct daylight-saving conversion for Melbourne.

### 16.2 Immediate alerts

- P0 market-moving event;
- P1 qualified opportunity;
- major thesis invalidation;
- paper-trade state change;
- stop/target event;
- data-provider outage affecting confidence;
- risk gate activation.

### 16.3 Alert format

```text
🔴 P0｜META｜Earnings / Guidance

What happened:
Why it matters:

Price:
Relative volume:
Options:
Industry:

Quality:
Valuation:
Opportunity:
Timing:

Confirmation:
Invalidation:
Status:

[Full analysis] [Watch] [Paper monitor] [Mute]
```

### 16.4 Anti-noise rules

- deduplicate;
- rate-limit;
- group related updates;
- suppress low-confidence signals;
- do not resend unchanged information;
- preserve delivery status and error.

---

## 17. Dashboard

### 17.1 Pages

1. Command Centre;
2. Today's Top 10;
3. Strategy Screener;
4. News Trading;
5. Institutional and Insider;
6. Intrinsic Value;
7. Unusual Options;
8. Watchlists;
9. Conditional Trade Plans;
10. Paper Trades;
11. Reports and Journal;
12. System Health;
13. Settings.

### 17.2 Command Centre

Must show:

- market regime;
- data freshness;
- provider health;
- daily funnel;
- Top 3;
- P0/P1 events;
- next scheduled event;
- paper-trading status;
- active risk blocks.

### 17.3 Valuation page

Must show side by side:

- Strict FCF Value;
- Normalised Owner Earnings Value;
- Multi-Model Fair Value;
- market price;
- pessimistic/base/optimistic;
- sensitivity;
- assumptions;
- confidence;
- model warnings.

---

## 18. Data Model

Minimum tables:

```text
symbols
symbol_classifications
market_prices_daily
market_prices_intraday
market_indicators
fundamentals
financial_statements
earnings_events
earnings_estimates
earnings_revisions
news_events
news_sources
news_symbol_links
sec_filings
institutional_managers
institutional_holdings
insider_transactions
short_interest
options_flow
social_mentions
market_regimes
screen_definitions
screen_runs
screen_results
stock_candidates
candidate_evidence
valuation_runs
valuation_assumptions
valuation_results
signal_scores
trade_plans
trade_plan_transitions
paper_trades
paper_trade_events
telegram_deliveries
reports
strategy_performance
provider_health
system_events
user_feedback
```

### 18.1 Required common fields

Where appropriate:

```text
id
symbol_id
source
source_url
source_timestamp
observed_at
effective_at
ingested_at
raw_payload_reference
schema_version
calculation_version
model_version
confidence
created_at
updated_at
```

### 18.2 No silent overwrite

Financial, valuation, score and signal history must be append-only or versioned. Recalculation must create a new run rather than rewrite history.

---

## 19. API Surface

Indicative endpoints:

```text
GET  /api/status
GET  /api/providers/health
GET  /api/market/regime
GET  /api/market/premarket-brief

POST /api/screens/run
GET  /api/screens
GET  /api/screens/{id}/results

GET  /api/candidates
GET  /api/candidates/{symbol}
POST /api/candidates/{symbol}/research
POST /api/candidates/{symbol}/feedback

POST /api/valuation/{symbol}/run
GET  /api/valuation/{symbol}/latest
GET  /api/valuation/{symbol}/history

GET  /api/news/events
POST /api/news/check
POST /api/news/{event_id}/analyse

GET  /api/institutions/{symbol}
GET  /api/insiders/{symbol}
GET  /api/options/{symbol}

POST /api/trade-plans
GET  /api/trade-plans
POST /api/trade-plans/{id}/transition

GET  /api/reports
GET  /api/strategy-performance
```

Mutating endpoints require authentication, authorisation and audit logging.

---

## 20. Scheduling

### 20.1 Continuous

- market-moving news;
- SEC filings;
- provider health;
- Telegram delivery health.

### 20.2 Pre-market

- macro and overnight events;
- earnings;
- gap and relative-volume candidates;
- estimate revisions;
- Top 10;
- Top 3;
- Chinese Telegram brief.

### 20.3 Market hours

- P0/P1 events;
- reaction-window checks;
- VWAP/opening-range verification;
- invalidation checks;
- paper monitoring in later phase.

### 20.4 After close

- outcomes;
- missed signals;
- event drift;
- watchlist rollover;
- daily report.

### 20.5 Weekend

- institutional updates;
- insider aggregation;
- valuation refresh;
- strategy statistics;
- data-quality audit;
- weekly report.

---

## 21. Security and Risk

### 21.1 Secrets

- environment variables or managed secret store;
- never logged;
- never returned through health endpoints;
- masked readiness reporting;
- separate paper and live credentials.

### 21.2 Trading safety

V1:

```text
CAN_TRADE = false
LIVE_TRADING_ENABLED = false
```

Later paper phase:

- explicit paper account verification;
- maximum position risk;
- daily loss limit;
- maximum concurrent positions;
- bracket protection;
- stale-data block;
- disconnected-broker block;
- trading-halt block;
- manual approval where configured.

### 21.3 AI safety

- structured schemas;
- source citations;
- numerical verification;
- prompt and model versioning;
- no AI authority to change risk configuration;
- no AI authority to reveal secrets;
- no AI authority to convert paper to live.

---

## 22. Testing

### 22.1 Unit tests

- filters;
- financial ratios;
- revision calculations;
- price indicators;
- scoring;
- DCF;
- safety margin;
- news deduplication;
- state transitions;
- risk rules.

### 22.2 Data-contract tests

Every provider adapter must be tested against:

- valid response;
- missing fields;
- changed field order;
- nulls;
- stale data;
- rate limiting;
- provider outage;
- duplicate records.

### 22.3 Historical replay

Replay known events:

- earnings beat and continuation;
- earnings beat and sell-the-news;
- guidance cut;
- merger announcement;
- Form 4 cluster purchase;
- 13D activist filing;
- high short interest without squeeze;
- unusual options hedge misclassification;
- false social rumour.

### 22.4 Valuation acceptance tests

At minimum:

- META high growth/high CapEx;
- stable cash-generative company;
- bank;
- REIT;
- unprofitable technology company;
- cyclical company.

Tests must validate model routing and warnings, not require all models to agree.

---

## 23. Performance Evaluation

For every signal, store outcomes at:

- 1 hour;
- close;
- 1 day;
- 5 days;
- 20 days;
- strategy-specific horizon.

Measure:

- maximum favourable excursion;
- maximum adverse excursion;
- hit rate;
- false-positive rate;
- average return;
- median return;
- drawdown;
- performance versus SPY;
- performance versus sector ETF;
- result by market regime;
- result by strategy;
- result by score band.

The system must not optimise thresholds using future information.

---

## 24. Development Phases

### Phase 0 — Specification and repository preparation

Deliver:

- implementation map;
- architecture decision records;
- provider interfaces;
- database migration plan;
- security model;
- test plan;
- environment template;
- local development instructions.

### Phase 1 — Stock Discovery MVP

Build:

- investable universe;
- daily market data;
- Finviz-style screening;
- Quality Growth Momentum;
- Earnings Revision Momentum where data permits;
- basic news and SEC ingestion;
- institutional/insider basics;
- four scores;
- Top 10 and Top 3;
- Chinese pre-market brief;
- Telegram;
- Supabase;
- simple dashboard;
- system health.

No broker execution.

### Phase 2 — Research and Valuation

Build:

- research agent workflow;
- filing and transcript analysis;
- full 13F/13D/13G/Form 4 parsing;
- institution profiles;
- three-method valuation engine;
- sensitivity;
- valuation confidence;
- Meta acceptance test;
- historical valuation records.

### Phase 3 — Trade with News

Build:

- real-time event classification;
- source tiers;
- Surprise Engine;
- affected-symbol graph;
- reaction windows;
- VWAP/opening-range confirmation;
- conditional trade plans;
- immediate Telegram alerts;
- event outcome review.

### Phase 4 — Options and Social

Build after provider decision:

- unusual options flow;
- spread/hedge likelihood;
- social acceleration;
- bot/noise reduction;
- cross-confirmation.

### Phase 5 — IBKR Paper Trading

Only after Phases 1–3 pass acceptance:

- IBKR paper connection;
- deterministic risk engine;
- bracket-order simulation;
- paper state machine;
- daily loss controls;
- paper reports;
- no live credentials.

### Phase 6 — Learning and Calibration

- strategy performance;
- score calibration;
- regime analysis;
- false-signal analysis;
- Leon feedback;
- controlled threshold changes;
- model governance.

### Phase 7 — Live Trading Review

Live trading is a separate project decision and requires:

- sufficient paper sample;
- documented performance;
- maximum drawdown review;
- failure-mode review;
- explicit Leon approval;
- separate credentials;
- hard live limits;
- manual kill switch.

---

## 25. Cost and Provider Policy

Start with minimum necessary spend.

Priority:

1. SEC EDGAR;
2. existing IBKR-accessible data;
3. one fundamentals/news provider;
4. Supabase Free where sufficient;
5. Telegram;
6. model APIs used selectively.

Potential expensive additions:

- professional real-time news;
- real-time unusual options;
- analyst estimate revisions;
- X API;
- premium market data.

Every paid provider requires:

- purpose;
- monthly and annual cost;
- trial result;
- substitute;
- expected improvement;
- Leon approval before payment.

No paid service may be activated automatically.

---

## 26. Definition of Done for V1

V1 is complete only when:

1. The system builds a reproducible investable universe.
2. It runs at least the core quality-growth and earnings-momentum screens.
3. Every candidate retains its strategy and evidence.
4. It produces Top 10 and Top 3 without forcing a trade.
5. It creates three distinct valuation perspectives.
6. It clearly displays valuation assumptions and confidence.
7. It monitors official news and SEC events.
8. It sends deduplicated Chinese Telegram reports.
9. It displays system and provider health.
10. It stores outcomes for later evaluation.
11. It has automated tests for core calculations.
12. It contains no live-trading capability.
13. Secrets are protected.
14. Missing data lowers confidence rather than producing fabricated values.
15. Meta valuation demonstrates the difference between reported FCF and normalised economics.

---

## 27. Codex Implementation Rules

Codex must:

- treat this document as the product source of truth;
- create an implementation map before coding;
- inspect an existing repository before changing it;
- preserve unrelated user changes;
- implement in small testable phases;
- use provider adapters;
- keep calculations deterministic;
- version schemas and scoring;
- include migrations;
- include tests;
- include sample data without secrets;
- provide clear run instructions;
- stop and request Leon's involvement only when login, payment, a material product decision or new authority is required.

Codex must not:

- enable live trading;
- invent unavailable API data;
- hard-code credentials;
- replace explicit risk rules with model judgement;
- silently change strategy thresholds;
- treat UI completion as system completion;
- claim a provider is working without a successful read-only test.

---

## 28. Final Product Definition

The final result is a continuously operating AI investment-research team that:

- scans the United States equity market;
- identifies companies experiencing meaningful change;
- verifies the change using independent evidence;
- evaluates company quality;
- examines institutional and insider behaviour;
- calculates intrinsic value using multiple economic perspectives;
- distinguishes long-term value from short-term timing;
- converts important news into conditional, risk-defined plans;
- alerts Leon only when the evidence warrants attention;
- records what happened afterwards;
- learns which strategies work in which market regimes.

The final product must be judged by the quality and auditability of its decisions, not by the number of alerts it produces.

---

## 29. Locked V1 Decisions

The following decisions are locked unless Leon explicitly changes them:

1. Default language is Chinese.
2. Initial market is United States equities.
3. V1 is research and decision support, not live trading.
4. Telegram is the priority alert channel.
5. Dashboard stores the complete evidence.
6. Kimi is a research worker, not the system controller.
7. Hermes is the orchestration layer.
8. Python performs calculations and rules.
9. Intrinsic value uses three distinct perspectives.
10. News cannot independently trigger a live order.
11. Institutional ownership is a confirmation factor, not the main engine.
12. Earnings revisions, quality, valuation and momentum form the core stock-selection framework.
13. Paid services require Leon's approval.

