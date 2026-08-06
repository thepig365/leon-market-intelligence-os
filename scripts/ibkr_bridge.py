#!/usr/bin/env python3
"""Send minimal paper-TWS status to LMIO without exposing the laptop or account data."""

from __future__ import annotations

import argparse
import os
import threading
import time
from datetime import UTC, datetime

import httpx
from ibapi.client import EClient
from ibapi.wrapper import EWrapper


class PaperTWSProbe(EWrapper, EClient):
    def __init__(self) -> None:
        EClient.__init__(self, self)
        self.ready = threading.Event()
        self.accounts: list[str] = []
        self.news_providers: list[dict[str, str]] = []
        self.error_message = ""

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
        if errorCode not in {2104, 2106, 2158}:
            self.error_message = f"TWS error {errorCode}"


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def collect_heartbeat(host: str, port: int, client_id: int) -> dict[str, object]:
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
        return {
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


def main() -> int:
    parser = argparse.ArgumentParser(description="LMIO outbound-only IBKR paper bridge")
    parser.add_argument("--once", action="store_true", help="send one heartbeat and exit")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=73)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("Refusing non-local TWS host")
    runtime_url = os.getenv("LMIO_RUNTIME_URL", "").strip()
    key = os.getenv("LMIO_IBKR_BRIDGE_KEY", "").strip()
    if not runtime_url or not key:
        raise SystemExit("LMIO_RUNTIME_URL and LMIO_IBKR_BRIDGE_KEY are required")
    while True:
        post_heartbeat(
            runtime_url,
            key,
            collect_heartbeat(args.host, args.port, args.client_id),
        )
        print(f"IBKR paper status sent at {datetime.now(UTC).isoformat()}")
        if args.once:
            return 0
        time.sleep(max(args.interval, 30))


if __name__ == "__main__":
    raise SystemExit(main())
