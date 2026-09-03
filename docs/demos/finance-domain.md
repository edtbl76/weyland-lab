# Demo — Finance domain (B113 Phase 1: FRED macro, land → mart → BI)

The finance data domain riding the mesh, FRED macro slice: ~13 macro series landed end-to-end and served through
the mesh's BI surfaces. Ingestion is the `datasets_lib` three-factory path (same as Music/Health); consumption is
**Lightdash + Superset + Cube** (not Grafana — that's observability). See
[design/finance-domain.md](../design/finance-domain.md), [diagrams/flow-finance-ingestion.md](../diagrams/flow-finance-ingestion.md),
and [query/finance.md](../query/finance.md).

## Prerequisites

- `weyland/fred-secret` sealed + present (FRED API key), mounted into `dagster-user-code` as `FRED_API_KEY`.
- `dagster-user-code` running the image with the finance assets (`group:datasets_finance` visible in Dagster).
- Trino/Iceberg, TimescaleDB, ClickHouse, DataHub, Lightdash, Superset, Cube up.

## CLI walkthrough — ingest the FRED slice

Materialize in Dagster (UI: **Assets → select group → Materialize**, or GraphQL `launchRun` on `__ASSET_JOB`).
Idempotent — a static full-history snapshot, safe to re-run.

1. **Land + transform (silver + gold):** materialize `group:datasets_finance`
   → `datasets_finance_fred_land` fetches **13 series / 40,930 observations** (FRED `"."` missing → NULL),
   then `parquet/arrow/avro/lance` silver + `iceberg` gold + the Nessie `commit`.
   Expect: 7 materializations, `series_ok=13`, `macro_rows=40,930`, `value` nulls ≈ 1,273.
2. **Store fan-out:** materialize `group:datasets_finance_stores`
   → `timescaledb_load` (hypertable `fred_macro`, 40,930 rows) + `clickhouse_load` (`fred_macro` 40,930 +
   `fred_series_meta` 13).
3. **dbt mart:** materialize `mart_macro_indicators`
   → `iceberg.dbt.mart_macro_indicators` — one row per series with `latest_value`, `prior_year_value`, `yoy_pct`.
4. **Catalog emit:** run `datahub_catalog_emit_job`
   → DataHub domain **Finance**, data product **Macro Indicators**, glossary **Finance Concepts** + 4 terms.

## Eyes-on UAT — confirm each surface renders the right data

**Trino (the source of truth for BI):**
```sql
SELECT series_id, title, latest_value, round(yoy_pct,2) AS yoy_pct
FROM iceberg.dbt.mart_macro_indicators ORDER BY series_id;
```
Confirm 13 rows: CPI ~332.8 (+3.3%), Unemployment 4.1% (−4.7%), Fed Funds 3.63% (−16.2%), Real GDP ~24,269.6 (+2.1%).

**Lightdash** — `https://lightdash.weyland.lab` → **Finance — marts overview**. Confirm the *Macro indicators —
latest value & YoY* table lists all 13 series with units, and the *Year-over-year change by indicator* bar shows
positive bars green-ward / negative (Fed Funds, Unemployment, Housing) the other way.

**Superset** — `https://superset.weyland.lab` → Dashboards → **Weyland Marts — Finance**. Confirm *Macro YoY by
indicator* and *Macro latest value by indicator* bars render over the `mart_macro_indicators` Trino dataset.

**Cube** — the `macro_indicators` cube (measures `count`, `latest_value`, `avg_yoy_pct`; dimensions `series_id`,
`title`, `units`, `frequency`, `seasonal_adjustment`). Check via the semantic-layer notebook (`41_semantic_cube.ipynb`)
or the Cube SQL API: `SELECT series_id, measure(avg_yoy_pct) FROM macro_indicators GROUP BY 1`.

**DataHub** — `https://datahub.weyland.lab` → Domains → **Finance** (21 assets) and Data Products → **Macro
Indicators** (8 assets); Glossary → **Finance Concepts** (Macro-Economic Indicator, YoY, Seasonal Adjustment,
Treasury Yield).

## Expected result

The 13 FRED macro series are queryable across Iceberg/Trino, TimescaleDB, and ClickHouse; the dbt mart serves
latest-value + YoY; three BI surfaces render it; DataHub catalogs the domain, product, and glossary. Grafana is
intentionally **not** a finance surface.

## Cleanup / teardown

Nothing to tear down — the snapshot is idempotent and reproducible from FRED. Re-materializing `group:datasets_finance`
refreshes it in place. Stores are truncate-and-reload on the store-load assets.
