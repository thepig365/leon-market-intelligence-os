# Authorised CSV Snapshot Import

LMIO accepts provider-neutral CSV exports so research can run before a paid or
credentialled API is approved. Only use data you are authorised to export and
process.

Required columns:

```text
symbol,company,observed_at,source,price,market_cap_m,average_dollar_volume_m
```

Recommended optional columns:

```text
source_url,country,exchange,is_common_stock,is_otc,revenue_growth_pct,
eps_growth_pct,gross_margin_pct,operating_margin_pct,roic_pct,debt_to_equity,
fcf_margin_pct,relative_strength_6m,price_above_200d_pct,
earnings_revision_30d_pct,earnings_surprise_pct,relative_volume,
sector_strength,data_completeness
```

`observed_at` must be an ISO-8601 timestamp with an offset. Blank optional
numbers remain missing and lower confidence; LMIO does not fabricate them.

Run:

```bash
uv run python -m lmio.cli import-csv --file /approved/path/snapshot.csv
```
