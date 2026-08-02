"""Trusted local CLI for reproducible LMIO workflows."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from lmio.config import get_settings
from lmio.providers.csv_snapshot import CSVSnapshotProvider
from lmio.providers.finviz_csv import FinvizCSVProvider
from lmio.providers.sec import SECProvider
from lmio.sec_monitor import monitor_sec
from lmio.service import LMIOService


def main() -> None:
    parser = argparse.ArgumentParser(description="LMIO local operations")
    parser.add_argument(
        "command",
        choices=(
            "backup",
            "demo-daily",
            "import-csv",
            "import-finviz",
            "meta-acceptance",
            "refresh-sec",
            "refresh-news",
            "research-latest",
            "status",
        ),
    )
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    service = LMIOService(get_settings())
    if args.command == "backup":
        if args.file is None:
            parser.error("--file is required for backup")
        payload = service.store.backup_export(args.file)
    elif args.command == "demo-daily":
        payload = service.run_demo_daily()
    elif args.command == "import-csv":
        if args.file is None:
            parser.error("--file is required for import-csv")
        provider = CSVSnapshotProvider()
        try:
            snapshots = provider.parse(args.file.read_text())
        except Exception as error:
            service.store.append_json(
                "provider_health",
                {
                    "provider": provider.name,
                    "state": "unavailable",
                    "payload": {"detail": type(error).__name__},
                },
            )
            raise
        health = provider.health()
        service.store.append_json(
            "provider_health",
            {
                "provider": health.provider,
                "state": health.state.value,
                "payload": {"detail": health.detail},
            },
        )
        payload = service.run_daily(snapshots, data_mode="authorised_csv")
    elif args.command == "import-finviz":
        if args.file is None:
            parser.error("--file is required for import-finviz")
        provider = FinvizCSVProvider()
        export_time = datetime.fromtimestamp(args.file.stat().st_mtime, tz=UTC)
        try:
            snapshots = provider.parse(
                args.file.read_text(),
                observed_at=export_time,
            )
        except Exception as error:
            service.store.append_json(
                "provider_health",
                {
                    "provider": provider.name,
                    "state": "unavailable",
                    "payload": {"detail": type(error).__name__},
                },
            )
            raise
        health = provider.health()
        service.store.append_json(
            "provider_health",
            {
                "provider": health.provider,
                "state": health.state.value,
                "payload": {"detail": health.detail},
            },
        )
        payload = service.run_daily(snapshots, data_mode=provider.name)
    elif args.command == "refresh-sec":
        settings = get_settings()
        payload = monitor_sec(
            SECProvider(settings.sec_user_agent),
            service.store,
            settings.parsed_sec_watchlist(),
        )
    elif args.command == "refresh-news":
        payload = service.refresh_official_news()
    elif args.command == "research-latest":
        payload = service.research_latest()
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
