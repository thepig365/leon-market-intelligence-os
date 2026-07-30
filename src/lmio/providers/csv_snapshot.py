"""Provider-neutral CSV snapshot import for authorised data exports."""

import csv
from datetime import UTC, datetime
from io import StringIO

from lmio.domain import SecuritySnapshot
from lmio.providers.base import Provider, ProviderHealth, ProviderState

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
    "data_completeness",
}


def _float_or_none(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


class CSVSnapshotProvider(Provider):
    name = "authorised_csv_snapshot"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            state=ProviderState.READY,
            detail="local import adapter",
        )

    def parse(self, content: str) -> list[SecuritySnapshot]:
        reader = csv.DictReader(StringIO(content))
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        items: list[SecuritySnapshot] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                values: dict[str, object] = {
                    "symbol": row["symbol"],
                    "company": row["company"],
                    "observed_at": datetime.fromisoformat(row["observed_at"]).astimezone(UTC),
                    "source": row["source"],
                    "source_url": row.get("source_url") or None,
                    "price": float(row["price"]),
                    "market_cap_m": float(row["market_cap_m"]),
                    "average_dollar_volume_m": float(row["average_dollar_volume_m"]),
                    "country": row.get("country") or "USA",
                    "exchange": row.get("exchange") or "NASDAQ",
                    "is_common_stock": (row.get("is_common_stock") or "true").lower() == "true",
                    "is_otc": (row.get("is_otc") or "false").lower() == "true",
                }
                for column in OPTIONAL_FLOAT_COLUMNS:
                    if column in row:
                        values[column] = _float_or_none(row[column])
                items.append(SecuritySnapshot.model_validate(values))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid CSV row {line_number}: {error}") from error
        if not items:
            raise ValueError("CSV contains no data rows")
        return items
