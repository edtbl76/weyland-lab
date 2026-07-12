-- MetricFlow time spine — one row per DAY (the finest granularity MetricFlow needs; it rolls up from here to
-- month/year). Trino generates the date series with sequence()+unnest; 2000–2035 covers every mart's `year`.
-- Materialized as an Iceberg table in iceberg.dbt so `mf query` can join against it.
{{ config(materialized='table') }}
select cast(d as date) as date_day
from unnest(sequence(date '2000-01-01', date '2035-12-31', interval '1' day)) as t(d)
