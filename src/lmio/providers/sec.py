"""Read-only SEC EDGAR submissions adapter."""

import json
from collections.abc import Callable
from typing import Any
from urllib import request

from lmio.providers.base import Provider, ProviderHealth, ProviderState

SEC_BASE_URL = "https://data.sec.gov"
Transport = Callable[[str, dict[str, str]], bytes]


def _urlopen_transport(url: str, headers: dict[str, str]) -> bytes:
    with request.urlopen(request.Request(url, headers=headers), timeout=15) as response:
        return response.read()


class SECProvider(Provider):
    name = "sec_edgar"

    def __init__(self, user_agent: str, transport: Transport | None = None) -> None:
        self.user_agent = user_agent.strip()
        self.transport = transport or _urlopen_transport

    def health(self) -> ProviderHealth:
        if not self.user_agent:
            return ProviderHealth(
                provider=self.name,
                state=ProviderState.DISABLED,
                detail="SEC_USER_AGENT is not configured",
            )
        try:
            payload = self._get("/submissions/CIK0000320193.json")
            if payload.get("cik") != "320193":
                return ProviderHealth(
                    provider=self.name,
                    state=ProviderState.DEGRADED,
                    detail="unexpected SEC response contract",
                )
        except Exception as error:  # provider boundary preserves a safe health result
            return ProviderHealth(
                provider=self.name,
                state=ProviderState.UNAVAILABLE,
                detail=type(error).__name__,
            )
        return ProviderHealth(provider=self.name, state=ProviderState.READY)

    def recent_filings(self, cik: str) -> list[dict[str, Any]]:
        normalised_cik = str(cik).lstrip("0").zfill(10)
        payload = self._get(f"/submissions/CIK{normalised_cik}.json")
        recent = payload.get("filings", {}).get("recent", {})
        required = ("accessionNumber", "filingDate", "form", "primaryDocument")
        if not all(isinstance(recent.get(field), list) for field in required):
            raise ValueError("SEC recent filing contract is incomplete")
        length = min(len(recent[field]) for field in required)
        return [
            {
                "cik": normalised_cik,
                "accession_number": recent["accessionNumber"][index],
                "filing_date": recent["filingDate"][index],
                "form": recent["form"][index],
                "primary_document": recent["primaryDocument"][index],
                "source": "SEC EDGAR",
            }
            for index in range(length)
        ]

    def _get(self, path: str) -> dict[str, Any]:
        if not self.user_agent:
            raise RuntimeError("SEC_USER_AGENT is required by SEC fair-access policy")
        raw = self.transport(
            f"{SEC_BASE_URL}{path}",
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            },
        )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("SEC response must be an object")
        return payload
