"""Dagster-free TimescaleDB time-axis coercion — shared by the hypertable loader.

Absolute imports only, no dagster, so the test lane loads it in isolation (conftest ``load_isolated``).

WHY THIS EXISTS: the TimescaleDB loader originally hardcoded ``pd.to_datetime(col, format="%Y")`` because
its only hypertable was WHO GHO, whose ``TimeDim`` is an integer YEAR. FRED's ``fred_macro`` hypertable
keys on a full ISO ``date`` — ``format="%Y"`` on ``"2024-03-01"`` coerces EVERY row to ``NaT``, which the
loader then drops, producing a silently-empty hypertable that still reports success (the exact
absent-result-as-success trap the lab's corrections warn about). This helper branches on dtype so both
shapes parse correctly, and it is unit-tested independently of the dagster runtime.
"""


def hypertable_ts(series):
    """Coerce a silver time column into a UTC ``timestamptz`` Series for a TimescaleDB hypertable.

    - NUMERIC column (WHO GHO ``TimeDim`` — an integer/float YEAR): interpreted as a year → Jan 1 of it.
    - Otherwise (a full date / ISO date string — FRED ``date``, stored as date32/object): parsed directly.

    Unparseable entries become ``NaT`` (the caller drops them — a hypertable time column must be non-null).
    """
    import pandas as pd

    if pd.api.types.is_numeric_dtype(series):
        # Integer/float YEAR → its string form → %Y. NaN years become "<NA>" → NaT (dropped downstream).
        years = series.astype("Int64").astype(str)
        return pd.to_datetime(years, format="%Y", errors="coerce", utc=True)
    # Full date / ISO string — let pandas infer (handles datetime.date, datetime64, "YYYY-MM-DD").
    return pd.to_datetime(series, errors="coerce", utc=True)
