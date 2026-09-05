"""Market OHLCV shaping for the daily-price lander (B113 Phase 4).

Dagster-free, pyarrow-only, absolute imports — loads in the light test lane in isolation (same contract as
``edgar_parse.py``/``market``). The lander fetches daily bars from yfinance (a pandas frame per ticker),
normalizes them to plain row dicts, and hands them here; this module drops incomplete bars and builds the
fixed ``price_daily`` silver schema that the Timescale hypertable, ClickHouse, Cassandra, and the dbt mart all
read.

Why the drop matters: yfinance returns today's **in-progress** bar with a NaN close (and often NaN OHLC) — a
bar without a real close is not a tradeable observation, and loading it would put NaN prices into the
hypertable + poison the mart's returns/volatility. Fail-closed on zero rows is the LANDER's job; this pure
builder just returns an empty table so that check has something honest to test.
"""
import math

import pyarrow as pa

# Phase 4: the single daily-price table. Joins the raw silver + Iceberg gold + Timescale/ClickHouse/Cassandra
# fan-out (declared here so the transform config imports one name, mirroring FILINGS_TEXT_TABLES / EDGAR_RAW_TABLES).
PRICE_TABLES = frozenset({"price_daily"})

_OHLC = ("open", "high", "low", "close")


def _missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def clean_price_rows(rows):
    """Drop any bar missing an OHLC value — yfinance's in-progress/holiday rows come back with NaN, and a bar
    without a real open/high/low/close is not an observation."""
    return [r for r in rows if not any(_missing(r.get(c)) for c in _OHLC)]


def build_price_table(rows):
    """Cleaned rows → the fixed ``price_daily`` Arrow schema. Empty input yields an empty (schema-correct)
    table; the lander fails closed if the whole fetch produced nothing."""
    rows = clean_price_rows(rows)

    def s(k):
        return [r.get(k) for r in rows]

    def f(k):
        return [None if _missing(r.get(k)) else float(r.get(k)) for r in rows]

    return pa.table({
        "ticker": pa.array(s("ticker"), type=pa.string()),
        "date": pa.array(s("date"), type=pa.date32()),
        "open": pa.array(f("open"), type=pa.float64()),
        "high": pa.array(f("high"), type=pa.float64()),
        "low": pa.array(f("low"), type=pa.float64()),
        "close": pa.array(f("close"), type=pa.float64()),
        "adj_close": pa.array(f("adj_close"), type=pa.float64()),
        "volume": pa.array([None if _missing(r.get("volume")) else int(r.get("volume")) for r in rows],
                           type=pa.int64()),
    })
