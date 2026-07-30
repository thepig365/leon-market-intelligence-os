# Authorised Current-Data Import

## Purpose

This is LMIO's zero-coupling path for a current market/fundamental export that
Leon is authorised to use. It does not scrape a website, bypass a provider API,
or grant LMIO permission to use a dataset.

## Gate

Before importing real data, record:

- provider or export owner;
- Leon's authority or licence to use the export;
- export timestamp and timezone;
- whether redistribution or storage restrictions apply;
- the approved local file path.

Do not place provider credentials or licensed source files in Git.

## Required columns

```text
symbol
company
observed_at
source
price
market_cap_m
average_dollar_volume_m
```

`observed_at` must be an ISO-8601 timestamp with a timezone. The trusted CLI
rejects snapshots more than 48 hours old, timestamps more than five minutes in
the future, duplicate symbols, ambiguous booleans, files over 20 MiB and files
over 20,000 rows.

## Optional columns

The template at `examples/authorised_snapshot_template.csv` lists every
supported optional field. Blank optional values remain missing. LMIO calculates
data completeness from the actual fields supplied and will not accept a
declared completeness value that exceeds the calculated value.

## Trusted import

```bash
uv run python -m lmio.cli import-csv --file /approved/path/snapshot.csv
```

The import:

1. validates and normalises every row before running screens;
2. records immutable source snapshots with timestamps and provenance;
3. deduplicates repeated imports by content;
4. updates the symbol directory;
5. lowers confidence where fields are missing;
6. produces research output only, never an order.

## Verification

After import:

```bash
uv run python -m lmio.cli status
```

Review provider health, input timestamps, daily funnel, missing-field
confidence and the generated report. A provider is not considered externally
verified until a successful authorised import is captured as evidence.
