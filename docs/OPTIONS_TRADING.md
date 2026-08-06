# Options Trading / 期权研究

This module identifies **research candidates**, not trades. It cannot create a
paper or live order and does not read account IDs, balances, positions or order
history.

## What Leon sees

- source, observation time and whether the data is delayed;
- contract, expiry, strike, Call/Put, volume, open interest and spread;
- the exact thresholds that passed or blocked the contract;
- whether the same contract passed twice within 2–30 minutes;
- a concise Telegram `/options` view for twice-confirmed candidates;
- explicit limitations and a permanent `CAN_TRADE = FALSE` boundary.

Default research gates are volume at least 500, open interest at least 100,
volume/OI at least 1.25, option price above USD 0.10, spread at most 20%, and
7–60 days to expiry. All gates must pass. Missing fields fail closed.

## Data routes

### Cboe most-active equity options (free, no login)

LMIO reads Cboe's official public most-active endpoint server-side. It stores a
bounded list of the leading equity-option Call and Put contracts, then groups
only those visible leaderboard rows by underlying ticker. The feed is delayed
by at least 20 minutes and covers the Cboe Options Exchange, not consolidated
US options volume.

This route does **not** provide bid, ask or open interest, so it does not enter
the unusual-contract classifier. It is a high-volume discovery list only. An
empty after-hours response never overwrites the last non-empty verified
snapshot. The dashboard's full Refresh action and the weekday scheduled job
both check this source without a subscription, credential or account login.

### IBKR paper TWS

`scripts/ibkr_bridge.py` uses the existing loopback-only paper TWS API. Basic
delayed quotes are requested without subscription-only generic ticks. When the
account lacks option volume or open-interest permission, LMIO records the
coverage gap and does not invent an unusual-volume candidate.

Generic option ticks may be enabled only after the relevant IBKR market-data
permission exists, using `--generic-option-ticks` or
`LMIO_OPTIONS_GENERIC_TICKS=true`. This does not enable trading.

### Barchart manual CSV

The protected Options Trading page accepts a CSV that Leon downloaded from
Barchart. LMIO does not log in to, scrape, automate, or bypass Barchart. The
upload is capped at 1 MB and 120 rows, parsed server-side and stored only when a
row reaches every research gate. Barchart credentials are never requested.

## Telegram

Send `/options` for the latest confirmed candidates and Cboe high-volume
tickers, or `/options SPY` for one symbol. Telegram messages say “non-trading
signal” and never contain buy, sell, position-size or order instructions.

## Interpretation limits

Unusual volume cannot prove whether activity opened or closed a position,
whether it came from an institution, or whether it is directional. Confirm with
the next session's open interest, the underlying price, company events and
liquidity. LMIO intentionally does not label this activity as a recommendation.
Likewise, appearing on Cboe's most-active leaderboard does not prove unusual
activity, direction or institutional intent.
