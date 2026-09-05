-- Mart: daily market prices (B113 Phase 4) — one row per ticker with the LATEST bar plus trailing-window
-- analytics: last close, last daily return, 30-trading-day return volatility (daily + annualized ×√252), and
-- the 52-week (252-trading-day) high/low with the pct off the high. Windowed per ticker over the daily bars,
-- then the latest bar (row_number desc = 1) is kept. Reads the finance Iceberg gold; dbt-trino writes this mart
-- back to Iceberg on Nessie `main` (marts = table, per dbt_project.yml).
{{ config(materialized='table') }}

with base as (
    select
        ticker,
        cast(date as date) as date,
        high,
        low,
        close,
        adj_close,
        volume
    from {{ source('datasets_finance', 'price_daily') }}
    where close is not null
),

enriched as (
    select
        ticker, date, high, low, close, adj_close, volume,
        (adj_close - lag(adj_close) over (partition by ticker order by date))
            / nullif(lag(adj_close) over (partition by ticker order by date), 0) as daily_return
    from base
),

windowed as (
    select
        ticker, date, close, adj_close, volume, daily_return,
        stddev_samp(daily_return) over (
            partition by ticker order by date rows between 29 preceding and current row
        ) as volatility_30d,
        max(high) over (
            partition by ticker order by date rows between 251 preceding and current row
        ) as high_52w,
        min(low) over (
            partition by ticker order by date rows between 251 preceding and current row
        ) as low_52w,
        row_number() over (partition by ticker order by date desc) as rn
    from enriched
)

select
    ticker,
    date as latest_date,
    close as latest_close,
    daily_return as latest_return,
    volatility_30d,
    volatility_30d * sqrt(252) as volatility_30d_annualized,
    high_52w,
    low_52w,
    case when high_52w is not null and high_52w <> 0
         then (close - high_52w) / high_52w end as pct_off_52w_high,
    volume as latest_volume
from windowed
where rn = 1
