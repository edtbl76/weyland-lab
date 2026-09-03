-- Mart: FRED macro indicators — one row per series with its latest observation and year-over-year change,
-- joined to the series dimension (title/units/frequency/seasonal adjustment). "Prior year" is the most
-- recent observation on or before one year before the latest date, so it works across FRED's mixed
-- frequencies (daily DGS10, monthly UNRATE, quarterly GDPC1). Reads the finance Iceberg gold; dbt-trino
-- writes this mart back to Iceberg on Nessie `main` (marts = table, per dbt_project.yml).
{{ config(materialized='table') }}

with macro as (
    select
        series_id,
        cast("date" as date) as obs_date,
        value
    from {{ source('datasets_finance', 'fred_macro') }}
    where value is not null
),

latest as (
    select series_id, max(obs_date) as latest_date
    from macro
    group by series_id
),

latest_val as (
    select m.series_id, m.obs_date as latest_date, m.value as latest_value
    from macro m
    join latest l on m.series_id = l.series_id and m.obs_date = l.latest_date
),

-- the most recent observation on or before one year before each series' latest date
prior as (
    select lv.series_id, max(m.obs_date) as prior_year_date
    from latest_val lv
    join macro m
      on m.series_id = lv.series_id
     and m.obs_date <= date_add('year', -1, lv.latest_date)
    group by lv.series_id
),

prior_val as (
    select p.series_id, p.prior_year_date, m.value as prior_year_value
    from prior p
    join macro m on m.series_id = p.series_id and m.obs_date = p.prior_year_date
)

select
    lv.series_id,
    meta.title,
    meta.units,
    meta.frequency,
    meta.seasonal_adjustment,
    lv.latest_date,
    lv.latest_value,
    pv.prior_year_date,
    pv.prior_year_value,
    case
        when pv.prior_year_value is not null and pv.prior_year_value <> 0
        then round((lv.latest_value - pv.prior_year_value) / pv.prior_year_value * 100.0, 2)
    end as yoy_pct
from latest_val lv
left join prior_val pv on lv.series_id = pv.series_id
left join {{ source('datasets_finance', 'fred_series_meta') }} meta
       on meta.series_id = lv.series_id
order by lv.series_id
