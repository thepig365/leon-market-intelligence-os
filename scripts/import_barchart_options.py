#!/usr/bin/env python3
"""Import one user-downloaded Barchart CSV without scraping or browser automation."""

from __future__ import annotations

import argparse
import csv
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx


def field(row: dict[str, str], *aliases: str) -> str:
    normalised = {key.strip().lower(): value.strip() for key, value in row.items() if key}
    return next((normalised[name.lower()] for name in aliases if normalised.get(name.lower())), "")


def number(value: str) -> float | None:
    cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned or cleaned in {"-", "N/A"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def expiry(value: str) -> str:
    for pattern in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unsupported expiration date: {value}")


def parse_csv(path: Path) -> list[dict[str, object]]:
    observed_at = datetime.now(UTC).isoformat()
    observations: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            symbol = field(row, "Symbol", "Underlying").upper()
            option_type = field(row, "Type", "Put/Call", "Call/Put").lower()
            strike = number(field(row, "Strike", "Strike Price"))
            expiration = field(row, "Exp Date", "Expiration", "Expiration Date")
            if not symbol or not strike or not expiration or option_type not in {"call", "put"}:
                continue
            observations.append(
                {
                    "symbol": symbol,
                    "expiry": expiry(expiration),
                    "strike": strike,
                    "right": option_type,
                    "observed_at": observed_at,
                    "source": "barchart_manual_csv",
                    "source_url": "https://www.barchart.com/options/unusual-activity",
                    "data_mode": "manual",
                    "delay_minutes": 30,
                    "underlying_price": number(field(row, "Price", "Underlying Price")),
                    "bid": number(field(row, "Bid")),
                    "ask": number(field(row, "Ask")),
                    "last": number(field(row, "Last", "Last Price")),
                    "volume": int(number(field(row, "Volume")) or 0),
                    "open_interest": int(number(field(row, "Open Int", "Open Interest")) or 0),
                    "implied_volatility": (
                        (number(field(row, "IV", "Implied Volatility")) or 0) / 100
                        if field(row, "IV", "Implied Volatility")
                        else None
                    ),
                    "delta": number(field(row, "Delta")),
                }
            )
    return observations[:120]


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a manually downloaded Barchart CSV")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    runtime_url = os.getenv("LMIO_RUNTIME_URL", "").strip()
    key = os.getenv("LMIO_ADMIN_API_KEY", "").strip()
    if not runtime_url or not key:
        raise SystemExit("LMIO_RUNTIME_URL and LMIO_ADMIN_API_KEY are required")
    observations = parse_csv(args.file)
    response = httpx.post(
        f"{runtime_url.rstrip('/')}/api/v1/providers/options/barchart-csv",
        headers={"x-lmio-key": key},
        json={"csv_text": args.file.read_text(encoding="utf-8-sig")},
        timeout=30,
    )
    response.raise_for_status()
    print(f"Imported {len(observations)} manually downloaded option rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
