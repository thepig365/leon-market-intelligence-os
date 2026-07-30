"""Trusted local CLI for reproducible LMIO workflows."""

import argparse
import json
from pathlib import Path

from lmio.config import get_settings
from lmio.providers.csv_snapshot import CSVSnapshotProvider
from lmio.providers.sec import SECProvider
from lmio.sec_monitor import monitor_sec
from lmio.service import LMIOService


def main() -> None:
    parser = argparse.ArgumentParser(description="LMIO local operations")
    parser.add_argument(
        "command",
        choices=("demo-daily", "import-csv", "meta-acceptance", "refresh-sec", "status"),
    )
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    service = LMIOService(get_settings())
    if args.command == "demo-daily":
        payload = service.run_demo_daily()
    elif args.command == "import-csv":
        if args.file is None:
            parser.error("--file is required for import-csv")
        snapshots = CSVSnapshotProvider().parse(args.file.read_text())
        payload = service.run_daily(snapshots, data_mode="authorised_csv")
    elif args.command == "refresh-sec":
        settings = get_settings()
        payload = monitor_sec(
            SECProvider(settings.sec_user_agent),
            service.store,
            settings.parsed_sec_watchlist(),
        )
    elif args.command == "meta-acceptance":
        payload = service.run_meta_acceptance()
    else:
        payload = {
            "counts": service.store.counts(),
            "safety": get_settings().public_health(),
            "integrations": get_settings().integration_readiness(),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
