-- Mart: WHO GHO population-health indicators by country x year, pivoted from the 8 per-indicator gold tables to
-- one wide row per (country, year). Each indicator is filtered to its country-total disaggregation (dim1 = null
-- or 'Both sexes'/'Total') and averaged (in case of multiple data sources). One row per (country, year).
{{ config(materialized='table') }}

{% set indicators = {
    'diabetes_prevalence': 'who_gho_diabetes',
    'adult_obesity': 'who_gho_obesity',
    'hypertension': 'who_gho_hypertension',
    'life_expectancy': 'who_gho_life_expectancy',
    'healthy_life_expectancy': 'who_gho_healthy_life_expectancy',
    'alcohol_consumption': 'who_gho_alcohol',
    'tobacco_smoking': 'who_gho_tobacco',
    'mental_health_disorders': 'who_gho_mental_health'
} %}

with gho as (
    {% for col, src in indicators.items() %}
    select
        '{{ col }}' as indicator,
        cast(spatialdim as varchar) as country,
        cast(timedim as integer) as year,
        numericvalue as val
    from {{ source('datasets_health', src) }}
    where numericvalue is not null
      and (dim1 is null or lower(trim(dim1)) in ('both sexes', 'total'))
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

agg as (
    select country, year, indicator, avg(val) as val
    from gho
    group by country, year, indicator
)

select
    country,
    year,
    {% for col in indicators.keys() %}
    max(case when indicator = '{{ col }}' then val end) as {{ col }}{% if not loop.last %},{% endif %}
    {% endfor %}
from agg
group by country, year
