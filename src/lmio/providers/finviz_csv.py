"""Normalise an authorised Finviz Elite screener export for LMIO."""

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from lmio.domain import SecuritySnapshot
from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import MarketDataProvider
from lmio.providers.csv_snapshot import MAX_CSV_BYTES, MAX_ROWS, SCORING_COLUMNS

REQUIRED_COLUMNS = {
    "Ticker",
    "Company",
    "Sector",
    "Industry",
    "Country",
    "Exchange",
    "Market Cap",
    "Average Volume",
    "Price",
}

FIELD_MAP = {
    "Sales Growth Quarter Over Quarter": "revenue_growth_pct",
    "EPS Growth Quarter Over Quarter": "eps_growth_pct",
    "Gross Margin": "gross_margin_pct",
    "Operating Margin": "operating_margin_pct",
    "Return on Invested Capital": "roic_pct",
    "Total Debt/Equity": "debt_to_equity",
    "Performance (Half Year)": "relative_strength_6m",
    "200-Day Simple Moving Average": "price_above_200d_pct",
    "EPS Surprise": "earnings_surprise_pct",
    "Relative Volume": "relative_volume",
    "Forward P/E": "forward_pe",
    "Institutional Transactions": "institutional_ownership_change_pct",
    "Relative Strength Index (14)": "rsi_14",
    "Short Float": "short_interest_float_pct",
    "Short Ratio": "days_to_cover",
}

EXCHANGE_MAP = {
    "AMEX": "AMEX",
    "NASD": "NASDAQ",
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "OTC": "OTC",
}

NON_COMMON_MARKERS = (
    "exchange traded fund",
    "closed-end fund",
    "shell companies",
    "warrant",
    "unit",
)


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    normalised = value.strip().replace(",", "")
    if not normalised or normalised == "-":
        return None
    if normalised.endswith("%"):
        normalised = normalised[:-1]
    return float(normalised)


def _is_common_stock(company: str, industry: str) -> bool:
    combined = f"{company} {industry}".lower()
    return not any(marker in combined for marker in NON_COMMON_MARKERS)


class FinvizCSVProvider(MarketDataProvider):
    """Parse a user-authenticated Finviz Elite CSV export without credentials."""

    name = "finviz_elite_csv"

    def __init__(self) -> None:
        self._verified = False
        self._accepted_rows = 0
        self._excluded_rows = 0

    def health(self) -> ProviderHealth:
        if not self._verified:
            return ProviderHealth(
                provider=self.name,
                state=ProviderState.CONFIGURED_NOT_VERIFIED,
                detail="awaiting a successful authorised Finviz Elite export parse",
            )
        return ProviderHealth(
            provider=self.name,
            state=ProviderState.READY,
            detail=(
                f"authorised Finviz export parsed: {self._accepted_rows} accepted, "
                f"{self._excluded_rows} excluded"
            ),
        )

    def parse(
        self,
        content: str,
        *,
        observed_at: datetime,
        now: datetime | None = None,
        max_age: timedelta = timedelta(hours=48),
    ) -> list[SecuritySnapshot]:
        if len(content.encode()) > MAX_CSV_BYTES:
            raise ValueError("Finviz CSV exceeds the configured size limit")
        if observed_at.tzinfo is None:
            raise ValueError("Finviz export time must include a timezone")
        observed_at = observed_at.astimezone(UTC)
        reference_time = (now or datetime.now(UTC)).astimezone(UTC)
        if observed_at > reference_time + timedelta(minutes=5):
            raise ValueError("Finviz export time is in the future")
        if reference_time - observed_at > max_age:
            raise ValueError("Finviz export is stale")

        reader = csv.DictReader(StringIO(content))
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Finviz CSV missing required columns: {', '.join(sorted(missing))}")

        items: list[SecuritySnapshot] = []
        excluded = 0
        seen_symbols: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            if line_number - 2 >= MAX_ROWS:
                raise ValueError("Finviz CSV exceeds the configured row limit")
            try:
                symbol = row["Ticker"].strip().upper()
                company = row["Company"].strip()
                country = row["Country"].strip()
                industry = row["Industry"].strip()
                raw_exchange = row["Exchange"].strip().upper()
                exchange = EXCHANGE_MAP.get(raw_exchange, raw_exchange)
                if not symbol or not company:
                    raise ValueError("ticker and company are required")
                if symbol in seen_symbols:
                    raise ValueError(f"duplicate symbol {symbol}")
                seen_symbols.add(symbol)

                is_common_stock = _is_common_stock(company, industry)
                is_otc = exchange == "OTC"
                price = _number(row["Price"])
                market_cap_m = _number(row["Market Cap"])
                average_volume_thousands = _number(row["Average Volume"])
                if (
                    not country
                    or not industry
                    or not exchange
                    or not is_common_stock
                    or is_otc
                    or price is None
                    or price <= 0
                    or market_cap_m is None
                    or market_cap_m <= 0
                    or average_volume_thousands is None
                    or average_volume_thousands < 0
                ):
                    excluded += 1
                    continue

                values: dict[str, object] = {
                    "symbol": symbol,
                    "company": company,
                    "observed_at": observed_at,
                    "source": "Finviz Elite authorised export",
                    "source_url": "https://elite.finviz.com/screener",
                    "price": price,
                    "market_cap_m": market_cap_m,
                    "average_dollar_volume_m": average_volume_thousands * price / 1000,
                    "country": country,
                    "exchange": exchange,
                    "is_common_stock": True,
                    "is_otc": False,
                }
                for finviz_field, lmio_field in FIELD_MAP.items():
                    if finviz_field in row:
                        values[lmio_field] = _number(row[finviz_field])
                if "Pattern" in row:
                    values["chart_pattern"] = row["Pattern"].strip() or None
                values["data_completeness"] = sum(
                    values.get(column) is not None for column in SCORING_COLUMNS
                ) / len(SCORING_COLUMNS)
                items.append(SecuritySnapshot.model_validate(values))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid Finviz CSV row {line_number}: {error}") from error

        if not items:
            raise ValueError("Finviz CSV contains no eligible equity rows")
        self._accepted_rows = len(items)
        self._excluded_rows = excluded
        self._verified = True
        return items

    def snapshots(self) -> list[SecuritySnapshot]:
        raise RuntimeError("Use parse(content, observed_at=...) with an authorised export.")
