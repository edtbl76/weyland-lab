-- Mart: Big Five (OCEAN) personality aggregated to country level from the per-respondent survey. Each of the 5
-- traits = mean of its 10 item responses (Likert 1-5), averaged over respondents per country. Approximate: raw
-- item means, no reverse-scoring of negatively-keyed items — fine for cross-country comparison, not clinical use.
-- Countries with < 30 respondents dropped. Joins to mart_country_health only via an ISO country crosswalk (TODO).
{{ config(materialized='table') }}

with resp as (
    select *
    from {{ source('datasets_health', 'big_five') }}
    where country is not null
      and country <> ''
      and e1 is not null   -- drops the header-as-row parse artifact (non-numeric -> null)
)

select
    country,
    count(*) as n_respondents,
    avg((e1 + e2 + e3 + e4 + e5 + e6 + e7 + e8 + e9 + e10) / 10.0) as extraversion,
    avg((n1 + n2 + n3 + n4 + n5 + n6 + n7 + n8 + n9 + n10) / 10.0) as neuroticism,
    avg((a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + a10) / 10.0) as agreeableness,
    avg((c1 + c2 + c3 + c4 + c5 + c6 + c7 + c8 + c9 + c10) / 10.0) as conscientiousness,
    avg((o1 + o2 + o3 + o4 + o5 + o6 + o7 + o8 + o9 + o10) / 10.0) as openness
from resp
group by country
having count(*) >= 30
