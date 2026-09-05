# TimescaleDB — query cookbook

**Connect:** `timescaledb.data-mesh.svc:5432`, db `timeseries` (user `weyland` / dev password). Postgres wire —
IntelliJ → PostgreSQL driver, port-forward the `timescaledb` svc `5432`. Also a **Grafana** datasource.

Hypertables (time-partitioned). Two families:
- **Platform metrics** (fed every 4h by Dagster `weyland_timeseries_job`): `eval_scores_ts`, `guardrail_verdicts_ts`,
  `dagster_run_durations`, `unleash_feature_metrics`, `datahub_ingestion_runs`.
- **WHO GHO** (8 `who_gho_*` hypertables, time axis = year → Jan 1).

### Explore
```sql
SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;
\d dagster_run_durations
```

### Platform metrics
```sql
-- Dagster run durations: daily avg by pipeline (time_bucket is the Timescale workhorse)
SELECT time_bucket('1 day', time) AS day, pipeline_name, avg(duration_seconds) AS avg_s, count(*) AS runs
FROM dagster_run_durations GROUP BY day, pipeline_name ORDER BY day DESC, avg_s DESC;

-- guardrail verdicts: decisions per validator, last 7 days
SELECT validator, decision, count(*) FROM guardrail_verdicts_ts
WHERE time > now() - interval '7 days' GROUP BY validator, decision ORDER BY validator;

-- eval scores: p50/p95 per metric
SELECT metric, percentile_cont(0.5) WITHIN GROUP (ORDER BY score) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY score) AS p95
FROM eval_scores_ts GROUP BY metric;

-- DataHub ingestion: success rate by source, last 30 days
SELECT source_type, source_name,
       count(*) FILTER (WHERE status = 'SUCCESS')::float / count(*) AS ok_rate
FROM datahub_ingestion_runs WHERE time > now() - interval '30 days'
GROUP BY source_type, source_name;
```

### WHO GHO (as time series)
```sql
-- life expectancy trend for a country (Timescale continuous view over the year axis)
SELECT time_bucket('1 year', ts) AS yr, avg(numericvalue) AS avg_val
FROM who_gho_life_expectancy WHERE spatialdim = 'USA' GROUP BY yr ORDER BY yr;
```

### FRED macro (finance)

`fred_macro` (B113 Phase 1) is a hypertable keyed on the real observation `date` (unlike WHO GHO's integer year).
~13 macro series long/tidy (`series_id`, `date`, `value`); `value` is NULL for FRED's `"."` gaps. Chunked at
**5 years** (a century of history at the 7-day default is thousands of chunks and crashes the backend on a group
over the time dimension — see the loader's `chunk_time_interval`).

```sql
-- confirm the hypertable + its chunk count
SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables
WHERE hypertable_name = 'fred_macro';

-- Fed funds rate, quarterly average via time_bucket (the Timescale workhorse)
SELECT time_bucket('3 months', date) AS quarter, avg(value) AS avg_fedfunds
FROM fred_macro
WHERE series_id = 'FEDFUNDS' AND value IS NOT NULL
GROUP BY quarter ORDER BY quarter DESC;
```

### Market prices (finance, B113 Phase 4)

`price_daily` is a hypertable on the trading `date` — full daily OHLCV history for the ~50 mega-caps (ticker,
date, open, high, low, close, adj_close, volume). The archetypal time-series: `time_bucket` for resampling,
window functions for returns.

```sql
-- monthly average close for one ticker
SELECT time_bucket('1 month', date) AS month, avg(close) AS avg_close
FROM price_daily WHERE ticker = 'AAPL'
GROUP BY month ORDER BY month DESC LIMIT 12;

-- 20-day simple moving average (window over the hypertable)
SELECT date, close,
       avg(close) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS sma20
FROM price_daily WHERE ticker = 'NVDA' ORDER BY date DESC LIMIT 30;
```

### Timescale-isms
- `time_bucket('<interval>', ts)` = the group-by-time primitive (like `date_trunc`, but hypertable-aware).
- `now() - interval '7 days'` for rolling windows; chunks make range scans fast.
- WHO GHO's `ts` is a derived `timestamptz` (year → Jan 1); the original `TimeDim` year is also kept.
