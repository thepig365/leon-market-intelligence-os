"""Provider-neutral CSV snapshot import for authorised data exports."""

import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from lmio.domain import SecuritySnapshot
from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import MarketDataProvider

REQUIRED_COLUMNS = {
    "symbol",
    "company",
    "observed_at",
    "source",
    "price",
    "market_cap_m",
    "average_dollar_volume_m",
}
OPTIONAL_FLOAT_COLUMNS = {
    "revenue_growth_pct",
    "eps_growth_pct",
    "gross_margin_pct",
    "operating_margin_pct",
    "roic_pct",
    "debt_to_equity",
    "fcf_margin_pct",
    "relative_strength_6m",
    "price_above_200d_pct",
    "earnings_revision_30d_pct",
    "earnings_surprise_pct",
    "relative_volume",
    "sector_strength",
    "forward_pe",
    "earnings_revision_breadth_pct",
    "institutional_ownership_change_pct",
    "activist_stake_pct",
    "insider_net_buying_m",
    "post_earnings_return_pct",
    "rsi_14",
    "short_interest_float_pct",
    "days_to_cover",
    "borrow_cost_pct",
    "news_impact_score",
}
OPTIONAL_INT_COLUMNS = {"days_since_earnings"}
SCORING_COLUMNS = {
    "revenue_growth_pct",
    "eps_growth_pct",
    "gross_margin_pct",
    "operating_margin_pct",
    "roic_pct",
    "debt_to_equity",
    "fcf_margin_pct",
    "relative_strength_6m",
    "price_above_200d_pct",
    "earnings_revision_30d_pct",
    "earnings_surprise_pct",
    "relative_volume",
    "sector_strength",
}
MAX_CSV_BYTES = 20 * 1024 * 1024
MAX_ROWS = 20_000


def _float_or_none(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def _int_or_none(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _strict_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalised = value.strip().lower()
    if normalised not in {"true", "false"}:
        raise ValueError("boolean fields must be true or false")
    return normalised == "true"


class CSVSnapshotProvider(MarketDataProvider):
    name = "authorised_csv_snapshot"

    def __init__(self) -> None:
        self._verified = False

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            state=(
                ProviderState.READY if self._verified else ProviderState.CONFIGURED_NOT_VERIFIED
            ),
            detail=(
                "authorised export parsed successfully"
                if self._verified
                else "awaiting a successful authorised export parse"
            ),
        )

    def parse(
        self,
        content: str,
        *,
        now: datetime | None = None,
        max_age: timedelta = timedelta(hours=48),
    ) -> list[SecuritySnapshot]:
        if len(content.encode()) > MAX_CSV_BYTES:
            raise ValueError("CSV exceeds the configured size limit")
        reference_time = now or datetime.now(UTC)
        if reference_time.tzinfo is None:
            raise ValueError("CSV reference time must include a timezone")
        reference_time = reference_time.astimezone(UTC)
        reader = csv.DictReader(StringIO(content))
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        items: list[SecuritySnapshot] = []
        seen_symbols: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            if len(items) >= MAX_ROWS:
                raise ValueError("CSV exceeds the configured row limit")
            try:
                observed_at = datetime.fromisoformat(row["observed_at"])
                if observed_at.tzinfo is None:
                    raise ValueError("observed_at must include a timezone")
                observed_at = observed_at.astimezone(UTC)
                if observed_at > reference_time + timedelta(minutes=5):
                    raise ValueError("observed_at is in the future")
                if reference_time - observed_at > max_age:
                    raise ValueError("snapshot is stale")
                symbol = row["symbol"].strip().upper()
                if not symbol:
                    raise ValueError("symbol is empty")
                if symbol in seen_symbols:
                    raise ValueError(f"duplicate symbol {symbol}")
                company = row["company"].strip()
                source = row["source"].strip()
                if not company or not source:
                    raise ValueError("company and source are required")
                values: dict[str, object] = {
                    "symbol": symbol,
                    "company": company,
                    "observed_at": observed_at,
                    "source": source,
                    "source_url": row.get("source_url") or None,
                    "price": float(row["price"]),
                    "market_cap_m": float(row["market_cap_m"]),
                    "average_dollar_volume_m": float(row["average_dollar_volume_m"]),
                    "country": row.get("country") or "USA",
                    "exchange": row.get("exchange") or "NASDAQ",
                    "is_common_stock": _strict_bool(row.get("is_common_stock"), True),
                    "is_otc": _strict_bool(row.get("is_otc"), False),
                }
                for column in OPTIONAL_FLOAT_COLUMNS:
                    if column in row:
                        values[column] = _float_or_none(row[column])
                for column in OPTIONAL_INT_COLUMNS:
                    if column in row:
                        values[column] = _int_or_none(row[column])
                if "chart_pattern" in row:
                    values["chart_pattern"] = row["chart_pattern"].strip() or None
                calculated_completeness = sum(
                    values.get(column) is not None for column in SCORING_COLUMNS
                ) / len(SCORING_COLUMNS)
                supplied_completeness = _float_or_none(row.get("data_completeness"))
                values["data_completeness"] = min(
                    calculated_completeness,
                    supplied_completeness
                    if supplied_completeness is not None
                    else calculated_completeness,
                )
                items.append(SecuritySnapshot.model_validate(values))
                seen_symbols.add(symbol)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid CSV row {line_number}: {error}") from error
        if not items:
            raise ValueError("CSV contains no data rows")
        self._verified = True
        return items

    def snapshots(self) -> list[SecuritySnapshot]:
        raise RuntimeError("Use parse(content) or the trusted CLI with an authorised export.")
