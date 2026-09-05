"""Tests for the dagster-free ``market_parse`` helper (B113 Phase 4 — market OHLCV).

The lander fetches daily bars from yfinance (a pandas frame per ticker) and hands normalized rows here. Two
things must hold: **incomplete bars are dropped** (yfinance returns today's in-progress bar with NaN close —
embedding/loading a NaN price is a silent-garbage bug), and the silver schema is fixed (ticker/date/OHLC/
adj_close/volume) so the Timescale hypertable, ClickHouse, Cassandra, and the dbt mart all read one shape.
Verified independent of the dagster runtime + yfinance.
"""
import datetime
import math


def _row(ticker="AAPL", d=datetime.date(2026, 9, 3), o=324.8, h=330.8, low=324.1, c=328.2, adj=328.2, v=37225800):
    return {"ticker": ticker, "date": d, "open": o, "high": h, "low": low, "close": c, "adj_close": adj, "volume": v}


def test_drops_bars_with_nan_close(market_parse):
    rows = [_row(), _row(d=datetime.date(2026, 9, 4), c=float("nan"), adj=float("nan"))]  # today's partial bar
    out = market_parse.clean_price_rows(rows)
    assert len(out) == 1
    assert out[0]["date"] == datetime.date(2026, 9, 3)


def test_drops_bars_with_none_ohlc(market_parse):
    rows = [_row(), _row(d=datetime.date(2026, 9, 2), o=None)]
    out = market_parse.clean_price_rows(rows)
    assert len(out) == 1 and out[0]["open"] is not None


def test_keeps_complete_bars_and_preserves_values(market_parse):
    rows = [_row(c=328.2, v=37225800)]
    out = market_parse.clean_price_rows(rows)
    assert out[0]["close"] == 328.2 and out[0]["volume"] == 37225800


def test_build_table_has_fixed_schema(market_parse):
    import pyarrow as pa

    tbl = market_parse.build_price_table([_row(), _row(ticker="MSFT", d=datetime.date(2026, 9, 3))])
    assert tbl.num_rows == 2
    schema = {f.name: str(f.type) for f in tbl.schema}
    assert schema["ticker"] == "string"
    assert schema["date"] == "date32[day]"
    assert schema["close"] == "double" and schema["adj_close"] == "double"
    assert schema["volume"] == "int64"
    assert pa.types.is_floating(tbl.schema.field("open").type)


def test_build_table_cleans_then_builds(market_parse):
    # a NaN-close bar handed straight to build must not survive into the table
    rows = [_row(), _row(d=datetime.date(2026, 9, 4), c=float("nan"))]
    tbl = market_parse.build_price_table(rows)
    assert tbl.num_rows == 1
    assert not any(math.isnan(v) for v in tbl.column("close").to_pylist())


def test_empty_after_cleaning_yields_empty_table_not_crash(market_parse):
    tbl = market_parse.build_price_table([_row(c=float("nan"))])
    assert tbl.num_rows == 0  # caller (lander) fails closed on zero rows, not this pure builder
