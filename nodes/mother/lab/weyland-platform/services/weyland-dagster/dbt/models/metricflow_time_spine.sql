-- MetricFlow time spine — one row per DAY (the finest granularity MetricFlow needs; it rolls up from here to
-- month/year). Trino generates the date series with sequence()+unnest; 2000–2035 covers every mart's `year`.
-- Materialized as an Iceberg table in iceberg.dbt so `mf query` can join against it. Range kept to 2000–2026
-- (~9.8k days) because Trino's sequence() rejects >10,000 entries; still covers every mart's year.
{{ config(materialized='table') }}
select cast(d as date) as date_day
from unnest(sequence(date '2000-01-01', date '2026-12-31', interval '1' day)) as t(d)
