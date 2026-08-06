# IBKR paper TWS local bridge

The bridge lets the protected LMIO dashboard show whether Leon's local paper
Trader Workstation is connected. It is a status bridge, not a trading engine.

## Safety design

- The laptop makes an outbound HTTPS request; no laptop port is exposed.
- TWS is contacted only at `127.0.0.1:7497`.
- Only connection state, paper-account confirmation, provider names and a
  timestamp leave the laptop.
- Account identifiers are reduced locally to a boolean and never transmitted.
- Balances, positions, orders, machine identifiers and news content are not in
  the accepted schema. Extra fields are rejected.
- The heartbeat has a dedicated secret and becomes stale after three minutes.
- `CAN_TRADE`, `LIVE_TRADING_ENABLED` and `PAPER_TRADING_ENABLED` remain false.
- LMIO has no order endpoint or order adapter.

## Local prerequisites

Install the official IBKR TWS API into the project virtual environment after
accepting IBKR's licence. The project deliberately does not redistribute it or
install an unofficial PyPI copy. In paper TWS, enable socket clients on port
7497. Enabling TWS paper API permission does not enable LMIO order execution.

Keep `LMIO_IBKR_BRIDGE_KEY` in the runtime's protected environment and the
local macOS Keychain or a private local environment. Never commit it.

The local bridge automatically reads the Keychain item whose service is
`LMIO_IBKR_BRIDGE_KEY` and account is `lmio-local-bridge` when the environment
variable is absent.

## Run one verification heartbeat

```bash
LMIO_RUNTIME_URL=https://protected-runtime.example \
LMIO_IBKR_BRIDGE_KEY=stored-secret \
LMIO_IBKR_PAPER_ORDER_PERMISSION_CONFIRMED=true \
.venv/bin/python scripts/ibkr_bridge.py --once
```

For continuous status, omit `--once`. The default interval is 60 seconds. If
the bridge stops, the dashboard marks the status stale rather than continuing
to claim that TWS is connected.
