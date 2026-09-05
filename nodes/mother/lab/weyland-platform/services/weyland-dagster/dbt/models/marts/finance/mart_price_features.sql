-- Mart: per-(ticker, date) MODELLING FEATURES for the Phase-5 ML lane (B113). Trailing, as-of-date features
-- only (NO forward-looking columns — the target lives in the training-set asset's entity_df, not here, so Feast
-- can serve these online without leakage): lagged returns (1/5/20d), trailing realized volatility (5/10/20d),
-- relative volume, mean intraday range, and price-vs-SMA. The warmup window (first ~20 bars per ticker, where the
-- 20-day stats are undefined) is dropped. This mart is loaded into the Feast offline store (feast Postgres) by
-- scripts/feast_setup.py and exposed as the `price_features` FeatureView. Reads the finance Iceberg gold.
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
    where close is not null and adj_close is not null
),

ret as (
    select
        ticker, date, high, low, close, adj_close, volume,
        adj_close / nullif(lag(adj_close, 1) over (partition by ticker order by date), 0) - 1 as ret_1d,
        adj_close / nullif(lag(adj_close, 5) over (partition by ticker order by date), 0) - 1 as ret_5d,
        adj_close / nullif(lag(adj_close, 20) over (partition by ticker order by date), 0) - 1 as ret_20d
    from base
),

feat as (
    select
        ticker, date, ret_1d, ret_5d, ret_20d,
        stddev_samp(ret_1d) over (partition by ticker order by date rows between 4 preceding and current row) as vol_5d,
        stddev_samp(ret_1d) over (partition by ticker order by date rows between 9 preceding and current row) as vol_10d,
        stddev_samp(ret_1d) over (partition by ticker order by date rows between 19 preceding and current row) as vol_20d,
        volume / nullif(avg(volume) over (partition by ticker order by date rows between 19 preceding and current row), 0) as volume_ratio,
        avg((high - low) / nullif(close, 0)) over (partition by ticker order by date rows between 19 preceding and current row) as range_20d,
        adj_close / nullif(avg(adj_close) over (partition by ticker order by date rows between 19 preceding and current row), 0) - 1 as sma_ratio_20d
    from ret
)

select ticker, date, ret_1d, ret_5d, ret_20d, vol_5d, vol_10d, vol_20d, volume_ratio, range_20d, sma_ratio_20d
from feat
where ret_20d is not null and vol_20d is not null   -- drop the warmup window (undefined trailing stats)
