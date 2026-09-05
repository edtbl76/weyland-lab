"""Tests for the dagster-free ``ml_targets`` forward-target helper (B113 Phase 5 — the ML lane).

The forward volatility target is the leakage-prone step: the label at date t must be the realized vol of the
returns AFTER t, aligned to t, with no bleed across tickers and the tail (no full forward window) dropping to
NaN. An off-by-one here silently poisons the model with lookahead. These pin the alignment against an
independent oracle.
"""
import datetime


def _series(ticker, prices, start=datetime.date(2026, 1, 1)):
    import pandas as pd
    return pd.DataFrame({
        "ticker": ticker,
        "date": [start + datetime.timedelta(days=i) for i in range(len(prices))],
        "adj_close": prices,
    })


def test_forward_vol_aligns_to_next_n_returns(ml_targets):
    import pandas as pd

    prices = [100, 101, 103, 102, 105, 104, 108, 110, 109, 112, 115, 113]
    df = ml_targets.forward_vol_target(_series("AAPL", prices), n=5).reset_index(drop=True)
    ret = pd.Series(prices).pct_change()   # index i = return on day i
    for t in (0, 1, 2):
        expected = float(ret.iloc[t + 1:t + 6].std(ddof=1))   # std of the NEXT 5 daily returns
        assert df.loc[t, "fwd_vol"] == _approx(expected)


def _approx(x):
    import pytest
    return pytest.approx(x, rel=1e-9)


def test_last_n_rows_are_nan(ml_targets):
    prices = list(range(100, 120))   # 20 bars
    df = ml_targets.forward_vol_target(_series("AAPL", prices), n=5).sort_values("date").reset_index(drop=True)
    assert df["fwd_vol"].iloc[-5:].isna().all()      # no full forward window for the last n
    assert df["fwd_vol"].iloc[:-5].notna().any()


def test_no_leakage_from_the_present_or_past(ml_targets):
    # changing price[t] and earlier must NOT change fwd_vol[t]; changing a FUTURE price must.
    base = [100, 101, 103, 102, 105, 104, 108, 110, 109, 112, 115, 113]
    a = ml_targets.forward_vol_target(_series("X", base), n=5).reset_index(drop=True)
    past = base.copy()
    past[0] = 50    # only the past/present of t=3
    b = ml_targets.forward_vol_target(_series("X", past), n=5).reset_index(drop=True)
    # fwd_vol[3] depends on returns 4..8, which are unchanged by price[0]
    assert a.loc[3, "fwd_vol"] == _approx(b.loc[3, "fwd_vol"])
    fut = base.copy()
    fut[6] = 200     # a future price inside t=3's window
    c = ml_targets.forward_vol_target(_series("X", fut), n=5).reset_index(drop=True)
    assert a.loc[3, "fwd_vol"] != _approx(c.loc[3, "fwd_vol"])


def test_tickers_computed_independently(ml_targets):
    import pandas as pd
    a = _series("AAPL", [100, 101, 103, 102, 105, 104, 108])
    b = _series("MSFT", [200, 190, 195, 210, 205, 215, 208])
    both = ml_targets.forward_vol_target(pd.concat([a, b], ignore_index=True), n=3)
    solo = ml_targets.forward_vol_target(a, n=3)
    m = both[both["ticker"] == "AAPL"].sort_values("date").reset_index(drop=True)
    s = solo.sort_values("date").reset_index(drop=True)
    assert (m["fwd_vol"].fillna(-1).round(9) == s["fwd_vol"].fillna(-1).round(9)).all()


def test_regime_label_splits_at_per_ticker_median(ml_targets):
    import pandas as pd
    df = pd.DataFrame({"ticker": ["A", "A", "A", "A"], "fwd_vol": [0.1, 0.2, 0.3, 0.4]})
    lab = ml_targets.regime_label(df)
    assert list(lab) == [0, 0, 1, 1]   # median 0.25 → 0.3/0.4 HIGH
