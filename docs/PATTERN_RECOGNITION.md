# LMIO Pattern Recognition

LMIO deliberately uses a small, explainable chart-pattern vocabulary:

1. Base Breakout
2. Ascending Triangle
3. Double Bottom
4. Uptrend Pullback

The initial implementation normalises explicit pattern labels from an
authorised Finviz export. It does not infer geometry from a screenshot and
does not claim that a breakout is confirmed without historical price, volume
and level data.

Every observation is shown as one of:

- forming;
- awaiting confirmation;
- confirmed;
- failed.

Until an authorised historical OHLCV provider is connected, imported Finviz
observations remain `awaiting_confirmation`. The dashboard exposes the
provider label, confirmation condition, invalidation condition and direct
Finviz chart link. A chart pattern is research evidence, not a trade
instruction, and cannot place an order.
