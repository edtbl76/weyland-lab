"""Market daily OHLCV — full price history for the finance mega-cap universe → finance/raw/price_daily/ (B113 Phase 4).

Prices for the SAME ~50 companies the XBRL/graph/filings slices cover, so a ticker joins financials, filings, the
company graph, AND its price series. Source is **yfinance** (Yahoo): the design's other free option, stooq, now
gates its CSV endpoint behind a JS proof-of-work wall, so a plain fetch gets HTML not data — yfinance's chart
API still serves clean daily bars (verified in-cluster). Trade-off: yfinance scrapes Yahoo, so it is more
fragile than an official API and can break when Yahoo changes — acceptable for a $0 lab, and the fetch fails
CLOSED (a ticker we could not fetch is skipped + logged; a price table with ZERO rows raises rather than
committing an empty raw layer).

One tidy raw table: ``price_daily`` (ticker, date, open, high, low, close, adj_close, volume) — the in-progress
bar (NaN close) and any incomplete row is dropped by ``market_parse``. `auto_adjust=False` keeps BOTH the raw
close and the split/dividend-adjusted `adj_close`.
"""
import io as _io
import time

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib.edgar_parse import select_ciks
from .datasets_lib.market_parse import build_price_table
from .finance_common import RefreshConfig, finance_minio, finance_put_parquet, should_skip

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_UA = "weyland-lab ed@timberbacklabs.com"
_YF_SLEEP = 0.5  # be polite to Yahoo between per-ticker downloads


def _get_json(url):
    import json
    import urllib.request

    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS URL: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": _SEC_UA})
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 — scheme asserted https; fixed SEC host
        return json.loads(r.read())


def _frame_to_rows(ticker, df):
    """yfinance daily frame → plain row dicts. A single-ticker `download` returns MultiIndex columns
    (('Close','AAPL')); flatten to the price level so the field lookups are stable."""
    if hasattr(df.columns, "get_level_values"):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    rows = []
    for idx, r in df.iterrows():
        rows.append({
            "ticker": ticker,
            "date": idx.date() if hasattr(idx, "date") else idx,
            "open": r.get("Open"), "high": r.get("High"), "low": r.get("Low"),
            "close": r.get("Close"), "adj_close": r.get("Adj Close"), "volume": r.get("Volume"),
        })
    return rows


def fetch_ticker(ticker):
    """Full daily history for one ticker as normalized rows (may be [] for a delisted/unknown symbol)."""
    import yfinance as yf

    df = yf.download(ticker, period="max", interval="1d", auto_adjust=False, progress=False, threads=False)
    if df is None or len(df) == 0:
        return []
    return _frame_to_rows(ticker, df)


@asset(group_name="datasets_finance",
       description="Land full daily OHLCV (yfinance) for the ~50 finance mega-caps → finance/raw/price_daily/.")
def datasets_finance_market_land(context, config: RefreshConfig) -> Output[dict]:
    if should_skip(context, config):  # materialize with {"force": true} to bypass the local freshness age
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})

    tickers = _get_json(_TICKERS_URL)
    universe = select_ciks(tickers)   # raises (fail closed) if the ticker map came back empty
    context.log.info(f"market universe: {len(universe)} tickers")

    all_rows, out = [], {}
    for _cik, ticker, _company in universe:
        if not ticker:
            continue
        try:
            rows = fetch_ticker(ticker)
            all_rows.extend(rows)
            out[ticker] = len(rows)   # 0 = no history (delisted/unknown symbol), a valid outcome
            context.log.info(f"market {ticker}: {len(rows):,} bars")
            time.sleep(_YF_SLEEP)
        except Exception as e:  # noqa: BLE001 — one bad ticker must not sink the rest
            out[ticker] = f"ERROR: {e}"
            context.log.warning(f"market {ticker}: {e}")

    tickers_ok = sum(1 for v in out.values() if isinstance(v, int) and v > 0)
    tbl = build_price_table(all_rows)   # drops NaN/in-progress bars
    if tbl.num_rows == 0:
        # Every ticker failed or produced no complete bar — fail loudly rather than commit an empty raw layer.
        raise RuntimeError(f"market land produced zero price rows across {len(universe)} tickers: {out}")

    buf = _io.BytesIO()
    pq.write_table(tbl, buf)
    client = finance_minio()
    finance_put_parquet(client, "price_daily/price_daily.parquet", buf.getvalue())

    context.log.info(f"landed price_daily ({tbl.num_rows:,} bars) from {tickers_ok}/{len(universe)} tickers")
    return Output(out, metadata={
        "tickers_ok": MetadataValue.int(tickers_ok),
        "price_rows": MetadataValue.int(tbl.num_rows),
        "detail": MetadataValue.json(out),
    })
