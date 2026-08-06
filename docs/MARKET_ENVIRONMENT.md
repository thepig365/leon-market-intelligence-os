# Market Environment

LMIO classifies the market environment only when all minimum benchmark evidence is present.

## Minimum verified inputs

- SPY daily change from Leon's authorised Finviz Elite API export;
- QQQ daily change from the same point-in-time export;
- IWM daily change from the same point-in-time export;
- advancing-stock breadth calculated from accepted common-stock rows in that export;
- the latest published VIX close from Cboe's public VIX history CSV.

The stored record includes retrieval time, VIX observation date, breadth sample size, source
URLs, the deterministic classification and its confidence. It never stores the Finviz token.

## Fail-safe behaviour

LMIO returns `Unverified` with zero confidence when any benchmark is absent, breadth has fewer
than 100 valid observations, the Cboe response is malformed, or the latest VIX close is more
than five calendar days old. Candidate rankings remain research queues and cannot become trade
instructions.

## Current scope

The first operational version opens the minimum defensible classification path. Treasury yields,
DXY, USD/JPY, oil, gold, sector leadership and scheduled macro events remain optional enrichment
inputs. They must not be presented as verified until separately connected and tested.
