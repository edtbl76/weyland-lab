-- Mart: SEC EDGAR company financials (B113 Phase 2) — one row per company with the LATEST ANNUAL
-- (form='10-K', fp='FY') value of each us-gaap concept pivoted to columns. The latest annual per concept is
-- picked with a window (row_number over cik, concept ordered by period_end desc), then the long fact rows are
-- pivoted with conditional MAX so each concept becomes its own column. Joined to the company_meta dim for the
-- SIC classification. Reads the finance Iceberg gold; dbt-trino writes this mart back to Iceberg on Nessie
-- `main` (marts = table, per dbt_project.yml).
{{ config(materialized='table') }}

with annual as (
    select
        cik,
        ticker,
        company,
        concept,
        cast(period_end as date) as period_end,
        fy,
        value,
        row_number() over (
            partition by cik, concept
            order by cast(period_end as date) desc
        ) as rn
    from {{ source('datasets_finance', 'company_financials') }}
    where form = '10-K' and fp = 'FY' and value is not null
),

latest as (
    select cik, ticker, company, concept, period_end, fy, value
    from annual
    where rn = 1
),

pivoted as (
    select
        cik,
        max(ticker) as ticker,
        max(company) as company,
        max(fy) as fiscal_year,
        max(case when concept = 'revenue' then value end) as revenue,
        max(case when concept = 'net_income' then value end) as net_income,
        max(case when concept = 'assets' then value end) as assets,
        max(case when concept = 'liabilities' then value end) as liabilities,
        max(case when concept = 'stockholders_equity' then value end) as stockholders_equity,
        max(case when concept = 'eps_basic' then value end) as eps_basic,
        max(case when concept = 'shares_outstanding' then value end) as shares_outstanding
    from latest
    group by cik
)

select
    p.cik,
    p.ticker,
    p.company,
    m.sic,
    m.sic_description,
    p.fiscal_year,
    p.revenue,
    p.net_income,
    p.assets,
    p.liabilities,
    p.stockholders_equity,
    p.eps_basic,
    p.shares_outstanding
from pivoted p
left join {{ source('datasets_finance', 'company_meta') }} m on m.cik = p.cik
order by p.ticker
