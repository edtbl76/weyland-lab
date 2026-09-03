# Query cookbook — Finance domain (FRED macro, B113 Phase 1)

The **finance** data domain rides the same `datasets_lib` lakehouse as music/health (`[[trino]]`,
`[[datasets-lake]]`, design: [../design/finance-domain.md](../design/finance-domain.md)). **Phase 1** is the
**FRED** (Federal Reserve Economic Data) macro slice — two gold Iceberg tables plus the `mart_macro_indicators`
dbt mart. This file is **domain-oriented** (all the finance queries in one place); the underlying stores each have
their own cookbook (`[[trino]]`, `[[gizmosql]]`, `[[timescaledb]]`, `[[clickhouse]]`) — this one shows how to reach
the finance data on each.

## What's in Phase 1

| Table | Where | Grain | Columns |
|---|---|---|---|
| `fred_macro` | `iceberg.datasets_finance.fred_macro` | one row per (series, observation date) | `series_id`, `date`, `value` |
| `fred_series_meta` | `iceberg.datasets_finance.fred_series_meta` | one row per series | `series_id`, `title`, `units`, `frequency`, `seasonal_adjustment` |
| `mart_macro_indicators` | `iceberg.dbt.mart_macro_indicators` | one row per series | latest value + prior-year value + `yoy_pct`, joined to meta |

`fred_macro` is tidy/long — ~13 series (GDPC1, CPIAUCSL, CPILFESL, UNRATE, FEDFUNDS, DGS2, DGS10, MORTGAGE30US,
PCE, INDPRO, RSAFS, HOUST, M2SL) at their native mixed frequencies (daily DGS10, monthly UNRATE, quarterly GDPC1).
`value` carries genuine gaps: FRED encodes a missing observation as `"."`, which the lander maps to `NULL` — always
`WHERE value IS NOT NULL` for aggregates.

## Trino / Iceberg (the primary path)

Connect as in `[[trino]]` (CLI `kubectl -n data-mesh exec -it deploy/trino -- trino`, or IntelliJ over the
port-forwarded `trino` svc `8080`, user any / no password).

### Discover — names are per-file; introspect first
```sql
SHOW TABLES FROM iceberg.datasets_finance;          -- fred_macro, fred_series_meta
DESCRIBE iceberg.datasets_finance.fred_macro;
DESCRIBE iceberg.dbt.mart_macro_indicators;
```

### Latest value per series (curated — the mart already computes it)
```sql
SELECT series_id, title, units, latest_date, latest_value, yoy_pct
FROM iceberg.dbt.mart_macro_indicators
ORDER BY series_id;
```

### Latest value per series (raw — same result straight off fred_macro)
```sql
-- most recent non-null observation for each series, labelled from the dimension
WITH latest AS (
  SELECT series_id, max(date) AS latest_date
  FROM iceberg.datasets_finance.fred_macro
  WHERE value IS NOT NULL
  GROUP BY series_id
)
SELECT m.series_id, meta.title, meta.units, f.date AS latest_date, f.value AS latest_value
FROM latest m
JOIN iceberg.datasets_finance.fred_macro f
  ON f.series_id = m.series_id AND f.date = m.latest_date
LEFT JOIN iceberg.datasets_finance.fred_series_meta meta
  ON meta.series_id = m.series_id
ORDER BY m.series_id;
```

### Year-over-year CPI (headline inflation)
```sql
-- straight from the mart: yoy_pct is (latest - prior_year) / prior_year * 100
SELECT series_id, title, latest_date, latest_value, prior_year_value, yoy_pct
FROM iceberg.dbt.mart_macro_indicators
WHERE series_id IN ('CPIAUCSL', 'CPILFESL');   -- headline CPI + core CPI
```

```sql
-- CPI as a monthly YoY series computed from raw fred_macro (LAG over the monthly index)
WITH cpi AS (
  SELECT date, value,
         lag(value, 12) OVER (ORDER BY date) AS value_year_ago
  FROM iceberg.datasets_finance.fred_macro
  WHERE series_id = 'CPIAUCSL' AND value IS NOT NULL
)
SELECT date, value,
       round((value - value_year_ago) / value_year_ago * 100.0, 2) AS yoy_pct
FROM cpi
WHERE value_year_ago IS NOT NULL
ORDER BY date DESC
LIMIT 24;
```

### Unemployment-rate trend
```sql
-- UNRATE (monthly), most recent two years
SELECT date, value AS unemployment_rate
FROM iceberg.datasets_finance.fred_macro
WHERE series_id = 'UNRATE' AND value IS NOT NULL
ORDER BY date DESC
LIMIT 24;
```

### Yield-curve spread (10y minus 2y Treasury)
```sql
-- self-join two daily series on date; a negative spread is the classic inversion signal
SELECT t10.date,
       t10.value AS dgs10,
       t2.value  AS dgs2,
       round(t10.value - t2.value, 2) AS spread_10y_2y
FROM iceberg.datasets_finance.fred_macro t10
JOIN iceberg.datasets_finance.fred_macro t2
  ON t2.date = t10.date AND t2.series_id = 'DGS2'
WHERE t10.series_id = 'DGS10'
  AND t10.value IS NOT NULL AND t2.value IS NOT NULL
ORDER BY t10.date DESC
LIMIT 30;
```

### Series catalog (the dimension)
```sql
SELECT series_id, title, units, frequency, seasonal_adjustment
FROM iceberg.datasets_finance.fred_series_meta
ORDER BY series_id;
```

## TimescaleDB — the hypertable path

`fred_macro` is also loaded as a **TimescaleDB hypertable** (time axis = the real observation `date`, not a year —
unlike WHO GHO). Connect as in `[[timescaledb]]`: `timescaledb.data-mesh.svc:5432`, db `timeseries`, Postgres wire
(also a Grafana datasource — the "Macro & Markets" dashboard reads it here).

```sql
-- confirm the hypertable is present (name follows the silver table)
SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables
WHERE hypertable_name = 'fred_macro';

-- Fed funds rate, quarterly average via time_bucket (the Timescale workhorse)
SELECT time_bucket('3 months', date) AS quarter, avg(value) AS avg_fedfunds
FROM fred_macro
WHERE series_id = 'FEDFUNDS' AND value IS NOT NULL
GROUP BY quarter ORDER BY quarter DESC;
```

## GizmoSQL / DuckDB — embedded OLAP

The finance silver is materialised as persisted DuckDB base tables in the `datasets_finance` schema, served over
Arrow Flight SQL. Connect as in `[[gizmosql]]` (IntelliJ Arrow Flight SQL JDBC to `mother:31337`, or in-pod ADBC
to `grpc+tcp://gizmosql.data-mesh.svc:31337`).

```sql
-- the finance tables (GetTables surfaces base tables)
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema = 'datasets_finance' ORDER BY table_name;

-- observations per series (DuckDB does the aggregation locally)
SELECT series_id, count(*) AS n_obs, count(value) AS n_present
FROM datasets_finance.fred_macro
GROUP BY series_id ORDER BY n_obs DESC;
```

## ClickHouse — columnar OLAP

Both finance tables are also ingested into ClickHouse (db `datasets_finance`) via the native `s3()` path. Connect
as in `[[clickhouse]]` (`clickhouse.data-mesh.svc:8123` HTTP, or `/play` at `clickhouse.weyland.lab`).

```sql
SELECT name FROM system.tables WHERE database = 'datasets_finance';

SELECT series_id, min(date) AS first_obs, max(date) AS last_obs, count() AS n
FROM datasets_finance.fred_macro
GROUP BY series_id ORDER BY series_id;
```

## Notes

- **Mind the gaps.** `value` is NULL where FRED reported `"."`. Aggregates and YoY math must filter
  `value IS NOT NULL` (the mart already does).
- **Mixed frequencies.** The series are daily/monthly/quarterly in one long table — `mart_macro_indicators`
  computes YoY as "latest vs the most recent observation on or before one year earlier", so it works across all of
  them. Roll your own carefully if you bypass the mart.
- **Schemas drift.** Later phases add EDGAR/market datasets and more tiers; run `SHOW TABLES` /
  `DESCRIBE` before trusting a column. Treat these as starting points, not contracts.
- Single-node Trino, 4G heap — prefer `approx_distinct`, filter early, `LIMIT` while exploring (`[[trino]]`).
