#!/usr/bin/env python3
"""Send minimal paper-TWS status to LMIO without exposing the laptop or account data."""

from __future__ import annotations

import argparse
import os
import subprocess
import threading
import time
from datetime import UTC, date, datetime
from itertools import count
from typing import Any

import httpx
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


class PaperTWSProbe(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.accounts: list[str] = []
        self.news_providers: list[dict[str, str]] = []
        self.error_message = ""
        self.error_codes: list[int] = []
        self.error_summaries: list[str] = []
        self.option_diagnostics: dict[str, int] = {
            "stocks_resolved": 0,
            "underlying_quotes": 0,
            "chains_resolved": 0,
            "eligible_expiries": 0,
            "eligible_strikes": 0,
        }
        self.next_request_id = count(1000)
        self.contract_details: dict[int, list[object]] = {}
        self.contract_events: dict[int, threading.Event] = {}
        self.option_chains: dict[int, list[dict[str, Any]]] = {}
        self.chain_events: dict[int, threading.Event] = {}
        self.quotes: dict[int, dict[str, Any]] = {}
        self.market_data_types: dict[int, int] = {}

    def nextValidId(self, orderId: int) -> None:
        self.reqNewsProviders()

    def managedAccounts(self, accountsList: str) -> None:
        self.accounts = [item.strip() for item in accountsList.split(",") if item.strip()]

    def newsProviders(self, newsProviders: list[object]) -> None:
        self.news_providers = [
            {"code": str(item.code), "name": str(item.name)} for item in newsProviders
        ]
        self.ready.set()

    def error(self, reqId: int, errorCode: int, errorString: str, *args: object) -> None:
        # Current TWS API inserts ``errorTime`` before the numeric code, while
        # older clients use the original three-argument callback.
        actual_code = int(errorString) if isinstance(errorString, int) else int(errorCode)
        actual_message = str(args[0]) if isinstance(errorString, int) and args else str(errorString)
        if actual_code not in self.error_codes:
            self.error_codes.append(actual_code)
            self.error_summaries.append(f"{actual_code}: {actual_message[:180]}")
        if actual_code not in {2104, 2106, 2158, 10167, 10168}:
            self.error_message = f"TWS error {actual_code}"

    def contractDetails(self, reqId: int, contractDetails: object) -> None:
        self.contract_details.setdefault(reqId, []).append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        self.contract_events.setdefault(reqId, threading.Event()).set()

    def securityDefinitionOptionParameter(
        self,
        reqId: int,
        exchange: str,
        underlyingConId: int,
        tradingClass: str,
        multiplier: str,
        expirations: set[str],
        strikes: set[float],
    ) -> None:
        self.option_chains.setdefault(reqId, []).append(
            {
                "exchange": exchange,
                "underlying_con_id": underlyingConId,
                "trading_class": tradingClass,
                "multiplier": multiplier,
                "expirations": sorted(expirations),
                "strikes": sorted(float(item) for item in strikes),
            }
        )

    def securityDefinitionOptionParameterEnd(self, reqId: int) -> None:
        self.chain_events.setdefault(reqId, threading.Event()).set()

    def marketDataType(self, reqId: int, marketDataType: int) -> None:
        self.market_data_types[reqId] = marketDataType

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib: object) -> None:
        key = {1: "bid", 2: "ask", 4: "last", 66: "bid", 67: "ask", 68: "last"}.get(tickType)
        if key and price >= 0:
            self.quotes.setdefault(reqId, {})[key] = float(price)

    def tickSize(self, reqId: int, tickType: int, size: object) -> None:
        value = int(float(size))
        quote = self.quotes.setdefault(reqId, {})
        if tickType in {8, 74}:
            quote["volume"] = value
        elif tickType in {27, 28}:
            quote["open_interest"] = value
        elif tickType in {29, 30}:
            quote["option_volume"] = value

    def tickOptionComputation(
        self,
        reqId: int,
        tickType: int,
        tickAttrib: int,
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float,
    ) -> None:
        quote = self.quotes.setdefault(reqId, {})
        if 0 <= impliedVol < 20:
            quote["implied_volatility"] = float(impliedVol)
        if -1 <= delta <= 1:
            quote["delta"] = float(delta)

    def new_request(self) -> int:
        return next(self.next_request_id)

    def resolve_stock(self, symbol: str) -> object | None:
        request_id = self.new_request()
        event = self.contract_events.setdefault(request_id, threading.Event())
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        self.reqContractDetails(request_id, contract)
        event.wait(timeout=8)
        details = self.contract_details.get(request_id, [])
        if details:
            self.option_diagnostics["stocks_resolved"] += 1
        return details[0] if details else None

    def quote(
        self,
        contract: Contract,
        *,
        wait_seconds: float = 4.0,
        generic_ticks: str = "",
    ) -> dict[str, Any]:
        request_id = self.new_request()
        self.quotes[request_id] = {}
        self.reqMktData(request_id, contract, generic_ticks, False, False, [])
        time.sleep(wait_seconds)
        self.cancelMktData(request_id)
        return {
            **self.quotes.get(request_id, {}),
            "market_data_type": self.market_data_types.get(request_id),
        }

    def option_chain(self, symbol: str, stock_details: object) -> dict[str, Any] | None:
        request_id = self.new_request()
        event = self.chain_events.setdefault(request_id, threading.Event())
        stock_contract = stock_details.contract
        self.reqSecDefOptParams(
            request_id,
            symbol,
            "",
            stock_contract.secType,
            stock_contract.conId,
        )
        event.wait(timeout=10)
        chains = self.option_chains.get(request_id, [])
        smart = [item for item in chains if item["exchange"] == "SMART"]
        return (smart or chains or [None])[0]


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def load_bridge_key() -> str:
    """Read the bridge key from the environment or Leon's macOS Keychain."""

    supplied = os.getenv("LMIO_IBKR_BRIDGE_KEY", "").strip()
    if supplied:
        return supplied
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            "lmio-local-bridge",
            "-s",
            "LMIO_IBKR_BRIDGE_KEY",
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _selected_expiry(expirations: list[str]) -> str | None:
    today = date.today()
    suitable: list[tuple[int, str]] = []
    for value in expirations:
        try:
            parsed = datetime.strptime(value, "%Y%m%d").date()
        except ValueError:
            continue
        dte = (parsed - today).days
        if 7 <= dte <= 60:
            suitable.append((dte, value))
    return min(suitable)[1] if suitable else None


def collect_options(
    probe: PaperTWSProbe,
    symbols: list[str],
    max_contracts_per_symbol: int,
    *,
    generic_option_ticks: bool = False,
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    probe.reqMarketDataType(3)
    for symbol in symbols[:10]:
        details = probe.resolve_stock(symbol)
        if details is None:
            continue
        underlying = probe.quote(details.contract, wait_seconds=3.0)
        underlying_price = underlying.get("last") or underlying.get("bid")
        if not underlying_price:
            continue
        probe.option_diagnostics["underlying_quotes"] += 1
        chain = probe.option_chain(symbol, details)
        if not chain:
            continue
        probe.option_diagnostics["chains_resolved"] += 1
        expiry = _selected_expiry(chain["expirations"])
        if not expiry:
            continue
        probe.option_diagnostics["eligible_expiries"] += 1
        strikes = sorted(
            (
                strike
                for strike in chain["strikes"]
                if float(underlying_price) * 0.88 <= strike <= float(underlying_price) * 1.12
            ),
            key=lambda strike: abs(strike - float(underlying_price)),
        )
        contract_limit = max(2, min(max_contracts_per_symbol, 20))
        strikes = strikes[: max(1, contract_limit // 2)]
        probe.option_diagnostics["eligible_strikes"] += len(strikes)
        for strike in strikes:
            for right in ("C", "P"):
                symbol_count = len([item for item in observations if item["symbol"] == symbol])
                if symbol_count >= contract_limit:
                    break
                contract = Contract()
                contract.symbol = symbol
                contract.secType = "OPT"
                contract.exchange = "SMART"
                contract.currency = "USD"
                contract.lastTradeDateOrContractMonth = expiry
                contract.strike = strike
                contract.right = right
                contract.multiplier = str(chain.get("multiplier") or "100")
                contract.tradingClass = str(chain.get("trading_class") or symbol)
                quote = probe.quote(
                    contract,
                    wait_seconds=1.0,
                    generic_ticks="100,101,106" if generic_option_ticks else "",
                )
                observed_at = datetime.now(UTC)
                observations.append(
                    {
                        "symbol": symbol,
                        "expiry": datetime.strptime(expiry, "%Y%m%d").date().isoformat(),
                        "strike": strike,
                        "right": "call" if right == "C" else "put",
                        "observed_at": observed_at.isoformat(),
                        "source": "ibkr_tws_paper_delayed",
                        "source_url": "https://www.interactivebrokers.com/",
                        "data_mode": "delayed",
                        "delay_minutes": 15,
                        "underlying_price": underlying_price,
                        "bid": quote.get("bid"),
                        "ask": quote.get("ask"),
                        "last": quote.get("last"),
                        "volume": quote.get("volume") or quote.get("option_volume"),
                        "open_interest": quote.get("open_interest"),
                        "implied_volatility": quote.get("implied_volatility"),
                        "delta": quote.get("delta"),
                    }
                )
    return observations


def collect_bridge_snapshot(
    host: str,
    port: int,
    client_id: int,
    symbols: list[str],
    max_contracts_per_symbol: int,
    *,
    generic_option_ticks: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    probe = PaperTWSProbe()
    connected = False
    try:
        probe.connect(host, port, clientId=client_id)
        thread = threading.Thread(target=probe.run, daemon=True)
        thread.start()
        connected = probe.ready.wait(timeout=12) and probe.isConnected()
        paper_confirmed = bool(probe.accounts) and all(
            account.upper().startswith("DU") for account in probe.accounts
        )
        heartbeat = {
            "observed_at": datetime.now(UTC).isoformat(),
            "connected": connected,
            "paper_account_confirmed": paper_confirmed,
            "paper_order_permission_confirmed": truthy(
                os.getenv("LMIO_IBKR_PAPER_ORDER_PERMISSION_CONFIRMED")
            ),
            "news_providers": probe.news_providers[:12],
            "headline_probe_count": 0,
            "bridge_version": "1",
        }
        observations = (
            collect_options(
                probe,
                symbols,
                max_contracts_per_symbol,
                generic_option_ticks=generic_option_ticks,
            )
            if connected
            else []
        )
        options = {
            "observed_at": datetime.now(UTC).isoformat(),
            "source": "ibkr_tws_paper_delayed",
            "observations": observations,
            "bridge_version": "2",
            "diagnostics": {
                **probe.option_diagnostics,
                "tws_error_codes": probe.error_codes,
                "tws_error_summaries": probe.error_summaries,
            },
        }
        return heartbeat, options
    finally:
        if probe.isConnected():
            probe.disconnect()


def post_heartbeat(runtime_url: str, key: str, payload: dict[str, object]) -> None:
    response = httpx.post(
        f"{runtime_url.rstrip('/')}/api/v1/providers/ibkr/heartbeat",
        headers={"x-lmio-ibkr-key": key},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def post_options(runtime_url: str, key: str, payload: dict[str, object]) -> None:
    response = httpx.post(
        f"{runtime_url.rstrip('/')}/api/v1/providers/ibkr/options",
        headers={"x-lmio-ibkr-key": key},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="LMIO outbound-only IBKR paper bridge")
    parser.add_argument("--once", action="store_true", help="send one heartbeat and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="probe local TWS and print field coverage without uploading data",
    )
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=73)
    parser.add_argument(
        "--symbols",
        default=os.getenv("LMIO_OPTIONS_WATCHLIST", "SPY,QQQ,AAPL"),
        help="comma-separated, maximum 10 symbols",
    )
    parser.add_argument(
        "--max-contracts-per-symbol",
        type=int,
        default=int(os.getenv("LMIO_OPTIONS_MAX_CONTRACTS_PER_SYMBOL", "12")),
    )
    parser.add_argument(
        "--generic-option-ticks",
        action="store_true",
        default=truthy(os.getenv("LMIO_OPTIONS_GENERIC_TICKS")),
        help=(
            "request option volume/OI/IV generic ticks only when the IBKR account "
            "has the required market-data permissions"
        ),
    )
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Refusing non-local TWS host")
    runtime_url = os.getenv("LMIO_RUNTIME_URL", "").strip()
    key = load_bridge_key()
    if not args.dry_run and (not runtime_url or not key):
        raise SystemExit("LMIO_RUNTIME_URL and LMIO_IBKR_BRIDGE_KEY are required")
    symbols = [
        item.strip().upper()
        for item in args.symbols.split(",")
        if item.strip() and item.strip().replace(".", "").isalnum()
    ][:10]
    while True:
        heartbeat, options = collect_bridge_snapshot(
            args.host,
            args.port,
            args.client_id,
            symbols,
            args.max_contracts_per_symbol,
            generic_option_ticks=args.generic_option_ticks,
        )
        if args.dry_run:
            observations = list(options["observations"])
            fields = (
                "bid",
                "ask",
                "last",
                "volume",
                "open_interest",
                "implied_volatility",
                "delta",
            )
            coverage = {
                field: sum(1 for item in observations if item.get(field) is not None)
                for field in fields
            }
            print(
                {
                    "connected": heartbeat["connected"],
                    "paper_account_confirmed": heartbeat["paper_account_confirmed"],
                    "symbols_requested": symbols,
                    "option_contracts_observed": len(observations),
                    "field_coverage": coverage,
                    "diagnostics": options["diagnostics"],
                    "uploaded": False,
                }
            )
            return 0
        options.pop("diagnostics", None)
        post_heartbeat(runtime_url, key, heartbeat)
        post_options(runtime_url, key, options)
        print(
            f"IBKR paper status and {len(options['observations'])} option snapshots sent "
            f"at {datetime.now(UTC).isoformat()}"
        )
        if args.once:
            return 0
        time.sleep(max(args.interval, 30))


if __name__ == "__main__":
    raise SystemExit(main())
