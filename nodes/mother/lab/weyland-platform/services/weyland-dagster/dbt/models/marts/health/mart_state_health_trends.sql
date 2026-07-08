-- Mart: chronic-condition prevalence by US state x year from BRFSS — the SQL version of feast_setup's
-- aggregation and the tested source for Feast state_health_risk (replaces the hand-rolled pandas pivot).
-- 'Overall' break-out, 'Yes' response, the 4 chronic conditions pivoted to columns. One row per (state, year).
-- (NHIS is per-respondent microdata, not state prevalence — deliberately not conformed into this mart.)
{{ config(materialized='table') }}

with base as (
    select state, year, topic, data_value
    from {{ ref('stg_brfss_prevalence') }}
    where break_out = 'Overall'
      and response = 'Yes'
)

select
    state,
    year,
    avg(case when topic = 'Diabetes' then data_value end) as diabetes_pct,
    avg(case when topic = 'Asthma' then data_value end) as asthma_pct,
    avg(case when topic = 'COPD' then data_value end) as copd_pct,
    avg(case when topic = 'Depression' then data_value end) as depression_pct
from base
group by state, year
