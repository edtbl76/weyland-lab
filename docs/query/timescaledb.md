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

### Timescale-isms
- `time_bucket('<interval>', ts)` = the group-by-time primitive (like `date_trunc`, but hypertable-aware).
- `now() - interval '7 days'` for rolling windows; chunks make range scans fast.
- WHO GHO's `ts` is a derived `timestamptz` (year → Jan 1); the original `TimeDim` year is also kept.
