"""Forward-looking ML targets for the finance ML lane (B113 Phase 5).

Dagster-free, pandas-only, absolute imports — loads in the light test lane in isolation. The forward target is
the leakage-prone part of the pipeline (an off-by-one in the forward window would either leak the present into
the label or mis-date it), so it lives here under test rather than inline in the Dagster asset.

``forward_vol_target``: per ticker, the realized volatility of the NEXT ``n`` daily returns, as-of each date.
``rolling(n).std()`` at index t+n is std(returns[t+1..t+n]); ``shift(-n)`` aligns that value back to t — so the
label at t depends ONLY on returns strictly after t, and the last n rows per ticker fall out as NaN.
"""
import pandas as pd


def forward_vol_target(df: pd.DataFrame, price_col: str = "adj_close", n: int = 5) -> pd.DataFrame:
    """Add a ``fwd_vol`` column = stddev of the daily returns on days t+1..t+n, per ticker. Assumes columns
    ``ticker`` + ``date`` + ``price_col``; returns a date-sorted copy."""
    df = df.sort_values(["ticker", "date"]).copy()
    df["_ret"] = df.groupby("ticker")[price_col].pct_change()
    df["fwd_vol"] = df.groupby("ticker")["_ret"].transform(lambda s: s.rolling(n).std().shift(-n))
    return df.drop(columns=["_ret"])


def regime_label(df: pd.DataFrame, target: str = "fwd_vol", by: str = "ticker") -> pd.Series:
    """HIGH(1)/LOW(0) split of ``target`` at each group's own median — so a classifier learns a per-name regime,
    not merely which name is high-vol."""
    med = df.groupby(by)[target].transform("median")
    return (df[target] > med).astype(int)
