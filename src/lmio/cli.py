"""Trusted local CLI for reproducible LMIO workflows."""

import argparse
import json

from lmio.config import get_settings
from lmio.service import LMIOService


def main() -> None:
    parser = argparse.ArgumentParser(description="LMIO local operations")
    parser.add_argument("command", choices=("demo-daily", "meta-acceptance", "status"))
    args = parser.parse_args()
    service = LMIOService(get_settings())
    if args.command == "demo-daily":
        payload = service.run_demo_daily()
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
