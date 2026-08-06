"""Read-only SEC EDGAR submissions adapter."""

import json
import re
from collections.abc import Callable
from typing import Any
from urllib import request
from urllib.parse import urlsplit

from lmio.providers.base import Provider, ProviderHealth, ProviderState

SEC_BASE_URL = "https://data.sec.gov"
SEC_DOCUMENT_HOSTS = {"www.sec.gov", "sec.gov"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_TICKER_MAP_BYTES = 5 * 1024 * 1024
Transport = Callable[[str, dict[str, str]], bytes]


def _is_safe_document_path(value: str) -> bool:
    parts = value.split("/")
    return bool(value) and all(
        part not in {"", ".", ".."} and re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts
    )


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
            if str(payload.get("cik")).lstrip("0") != "320193":
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

    def fetch_document(self, url: str) -> str:
        """Fetch one official SEC filing document with a bounded response size."""

        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in SEC_DOCUMENT_HOSTS:
            raise ValueError("SEC document URL must use an approved sec.gov HTTPS host")
        if not self.user_agent:
            raise RuntimeError("SEC_USER_AGENT is required by SEC fair-access policy")
        raw = self.transport(
            url,
            {
                "User-Agent": self.user_agent,
                "Host": parsed.hostname,
            },
        )
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError("SEC document exceeds the configured size limit")
        return raw.decode("utf-8", errors="replace")

    def ticker_ciks(self, symbols: set[str]) -> dict[str, str]:
        """Resolve an approved symbol set against the official SEC ticker directory."""

        if not self.user_agent:
            raise RuntimeError("SEC_USER_AGENT is required by SEC fair-access policy")
        wanted = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
        if not wanted:
            return {}
        raw = self.transport(
            "https://www.sec.gov/files/company_tickers.json",
            {"User-Agent": self.user_agent, "Host": "www.sec.gov"},
        )
        if len(raw) > MAX_TICKER_MAP_BYTES:
            raise ValueError("SEC ticker directory exceeds the configured size limit")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("SEC ticker directory must be an object")
        resolved: dict[str, str] = {}
        for item in payload.values():
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "")).upper()
            cik = str(item.get("cik_str", "")).lstrip("0")
            if ticker in wanted and cik.isdigit():
                resolved[ticker] = cik
        return resolved

    def ownership_document_url(self, filing: dict[str, Any]) -> str:
        """Resolve the parseable official ownership document for a filing."""

        cik = str(filing["cik"]).lstrip("0")
        accession = str(filing["accession_number"]).replace("-", "")
        base_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}"
        form = str(filing["form"]).upper()
        if not form.startswith("13F"):
            primary = str(filing["primary_document"])
            if not _is_safe_document_path(primary):
                raise ValueError("SEC primary document name is invalid")
            parts = primary.split("/")
            if len(parts) == 2 and parts[0].lower().startswith("xsl"):
                primary = parts[1]
            return f"{base_url}/{primary}"

        index = json.loads(self.fetch_document(f"{base_url}/index.json"))
        items = index.get("directory", {}).get("item", [])
        if not isinstance(items, list):
            raise ValueError("SEC filing directory contract is incomplete")
        candidates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            normalised = name.lower()
            if (
                re.fullmatch(r"[A-Za-z0-9_.-]+", name)
                and normalised.endswith(".xml")
                and "information" in normalised
                and "table" in normalised
            ):
                candidates.append(name)
        if len(candidates) != 1:
            raise ValueError("SEC 13F filing has no unique information-table XML")
        return f"{base_url}/{candidates[0]}"

    def _get(self, path: str) -> dict[str, Any]:
        if not self.user_agent:
            raise RuntimeError("SEC_USER_AGENT is required by SEC fair-access policy")
        raw = self.transport(
            f"{SEC_BASE_URL}{path}",
            {
                "User-Agent": self.user_agent,
                "Host": "data.sec.gov",
            },
        )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("SEC response must be an object")
        return payload
