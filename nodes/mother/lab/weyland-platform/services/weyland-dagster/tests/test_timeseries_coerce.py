"""Tests for the dagster-free ``timeseries.hypertable_ts`` helper (B113 Phase 1).

This helper is the fix for a real health→finance mapping bug: the TimescaleDB loader hardcoded
``format="%Y"`` (WHO GHO's TimeDim is a year), which would coerce EVERY full-date FRED row to NaT and
silently drop it, leaving an empty hypertable that still reported success. The helper branches on dtype so
both shapes parse — verified independently of the dagster runtime.
"""
import datetime


def test_numeric_year_column_becomes_jan_1(timeseries):
    # WHO GHO shape: an integer YEAR → Jan 1 of that year (the behaviour the old format="%Y" gave).
    import pandas as pd

    ts = timeseries.hypertable_ts(pd.Series([2016, 2018, 2024]))
    assert list(ts.dt.year) == [2016, 2018, 2024]
    assert list(ts.dt.month) == [1, 1, 1]
    assert list(ts.dt.day) == [1, 1, 1]


def test_float_year_with_nan_coerces_nan_to_nat(timeseries):
    import pandas as pd

    ts = timeseries.hypertable_ts(pd.Series([2016.0, None, 2020.0]))
    assert ts.iloc[0].year == 2016
    assert pd.isna(ts.iloc[1])          # NaN year → NaT (the caller drops it — time col must be non-null)
    assert ts.iloc[2].year == 2020


def test_iso_date_string_column_parses_the_full_date(timeseries):
    # FRED shape: a full ISO date must parse to THAT date, NOT be crushed to a year (the bug this fixes).
    import pandas as pd

    ts = timeseries.hypertable_ts(pd.Series(["2024-03-01", "2024-06-15"]))
    assert ts.iloc[0].date() == datetime.date(2024, 3, 1)
    assert ts.iloc[1].date() == datetime.date(2024, 6, 15)


def test_python_date_objects_parse(timeseries):
    # date32 → pandas gives datetime.date objects (object dtype) — must still parse to the same dates.
    import pandas as pd

    ts = timeseries.hypertable_ts(pd.Series([datetime.date(2023, 7, 1), datetime.date(2024, 1, 1)]))
    assert ts.iloc[0].date() == datetime.date(2023, 7, 1)
    assert ts.iloc[1].date() == datetime.date(2024, 1, 1)


def test_unparseable_date_string_becomes_nat_not_a_wrong_value(timeseries):
    import pandas as pd

    ts = timeseries.hypertable_ts(pd.Series(["2024-01-01", "garbage"]))
    assert ts.iloc[0].date() == datetime.date(2024, 1, 1)
    assert pd.isna(ts.iloc[1])


def test_result_is_utc_aware(timeseries):
    # The hypertable column is timestamptz — the coercion must be tz-aware (UTC), for both branches.
    import pandas as pd

    assert timeseries.hypertable_ts(pd.Series([2020])).dt.tz is not None
    assert timeseries.hypertable_ts(pd.Series(["2020-05-01"])).dt.tz is not None
