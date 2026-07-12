-- MetricFlow time spine — one row per DAY (the finest granularity MetricFlow needs; it rolls up from here to
-- month/year). Trino generates the date series with sequence()+unnest; 2000–2035 covers every mart's `year`.
-- Materialized as an Iceberg table in iceberg.dbt so `mf query` can join against it. Full daily calendar
-- 1960–2026 — WHO GHO life-expectancy data goes back to 1960, so the spine must too. Trino's sequence() caps at
-- 10,000 entries (a 1960–2026 daily sequence is ~24k), so we CROSS JOIN a years-sequence × a day-of-year-sequence
-- (each well under the cap), DISTINCT the dates, and trim the overshoot past 2026.
{{ config(materialized='table') }}
select distinct cast(dt as date) as date_day
from (
    select date_add('day', doy.n, date_add('year', yr.n, date '1960-01-01')) as dt
    from unnest(sequence(0, 66)) as yr(n)
    cross join unnest(sequence(0, 365)) as doy(n)
) g
where dt <= date '2026-12-31'
