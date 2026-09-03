"""Dagster-free FRED parse + shape helpers for the finance domain (B113 Phase 1).

Deliberately self-contained: ONLY absolute imports, NO ``from . import ...`` and NO dagster — the same
rule ``parquet_read.py`` follows so the test lane can load this module in isolation (conftest's
``load_isolated``) with just pyarrow, never the dagster runtime. The land asset in
``datasets_finance_fred_land.py`` does the network fetch and hands the raw JSON to these pure functions;
the finance ``DomainConfig`` in ``datasets_finance_transform.py`` imports the allowlist constants below so
the config's knobs and the silver schema stay in one grep-able, unit-testable place.

FRED API shapes (confirmed live 2026-09-02):
  - series metadata:     {"seriess": [{id, title, units, frequency, seasonal_adjustment, ...}]}
  - series observations: {"observations": [{realtime_start, realtime_end, date, value}, ...], "count": N}

The load-bearing gotcha: ``value`` is a STRING, and a MISSING observation arrives as the literal ``"."``.
``parse_fred_value`` maps ``"."`` (and blanks) to ``None`` and everything else to ``float`` — a naive
``float(v)`` would raise on ``"."`` and sink the whole series.
"""
from datetime import date, datetime

import pyarrow as pa

# --- finance domain declarative knobs (imported by datasets_finance_transform.py's DomainConfig) --------
# The 13 macro series landed in Phase 1. Order is stable so the stacked fred_macro table is deterministic.
SERIES_IDS = (
    "GDPC1",        # Real Gross Domestic Product
    "CPIAUCSL",     # Consumer Price Index (all urban consumers)
    "CPILFESL",     # Core CPI (less food & energy)
    "UNRATE",       # Unemployment rate
    "FEDFUNDS",     # Effective federal funds rate
    "DGS2",         # 2-Year Treasury constant maturity
    "DGS10",        # 10-Year Treasury constant maturity
    "MORTGAGE30US", # 30-Year fixed mortgage average
    "PCE",          # Personal consumption expenditures
    "INDPRO",       # Industrial production index
    "RSAFS",        # Advance retail sales
    "HOUST",        # Housing starts
    "M2SL",         # M2 money stock
)

# raw/ folder names the broker fans out (table per folder). Both are single-file folders.
FRED_MACRO = "fred_macro"
FRED_SERIES_META = "fred_series_meta"
RAW_TABLES = frozenset({FRED_MACRO, FRED_SERIES_META})

# TimescaleDB (Phase 1): one hypertable — fred_macro — with the time axis on the real observation `date`
# (a full ISO date, NOT a year like WHO GHO's TimeDim). The generalized coercion lives in timeseries.py.
TIMESCALE_TIME_COL = "date"
TIMESCALE_ALLOW = {FRED_MACRO: TIMESCALE_TIME_COL}

# ClickHouse (Phase 1): both tables — native s3() ingest of the silver parquet.
CLICKHOUSE_ALLOW = frozenset({FRED_MACRO, FRED_SERIES_META})

# Iceberg gold (Phase 1): both tables — what the dbt mart reads.
ICEBERG_ALLOW = frozenset({FRED_MACRO, FRED_SERIES_META})

# The explicit silver schemas — the code is the source of truth for what the broker writes.
MACRO_COLUMNS = ("series_id", "date", "value")
META_COLUMNS = ("series_id", "title", "units", "frequency", "seasonal_adjustment")


def parse_fred_value(v):
    """One FRED observation value → float or None.

    FRED encodes a MISSING observation as the literal string ``"."`` and every present value as a numeric
    string (``"4.1"``). Blank / whitespace-only / None also mean missing. A value that is neither ``"."``
    nor a parseable number is returned as None (rather than raising) so one bad cell cannot sink a series —
    the land asset counts nulls, so a wholesale-null series is still visible downstream.
    """
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s == ".":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_fred_date(v):
    """A FRED ``date`` string (``YYYY-MM-DD``) → a ``datetime.date``, or None if unparseable/empty."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def observations_to_rows(series_id, observations):
    """Shape one series' observations into tidy/long rows [{series_id, date, value}, ...].

    ``observations`` accepts either the raw API dict ({"observations": [...]}) or the list itself. Each
    output row carries the parsed ``date`` (datetime.date | None) and ``value`` (float | None). Rows whose
    date is unparseable are DROPPED — a long/tidy series keyed on (series_id, date) has no use for an
    undated point — while a valid date with a missing value ("." ) is KEPT with value=None (the gap is
    real information). An empty / missing observation list yields no rows.
    """
    if isinstance(observations, dict):
        observations = observations.get("observations") or []
    rows = []
    for obs in observations:
        d = parse_fred_date(obs.get("date"))
        if d is None:
            continue
        rows.append({"series_id": series_id, "date": d, "value": parse_fred_value(obs.get("value"))})
    return rows


def extract_series_meta(series_metadata):
    """Pull the finance dim fields from a FRED series metadata payload.

    Accepts the raw API dict ({"seriess": [{...}]}) or a single series dict. Returns
    {series_id, title, units, frequency, seasonal_adjustment} with missing fields as None. Raises
    ValueError when the payload carries no series object at all — a metadata call that returned nothing
    is a real failure, not an empty-but-fine result (fail closed, per the lab's silent-failure rule).
    """
    if isinstance(series_metadata, dict) and "seriess" in series_metadata:
        seriess = series_metadata.get("seriess") or []
        if not seriess:
            raise ValueError("FRED series metadata carried an empty 'seriess' list")
        s = seriess[0]
    elif isinstance(series_metadata, dict):
        s = series_metadata
    else:
        raise ValueError(f"unexpected FRED series metadata type: {type(series_metadata).__name__}")
    return {
        "series_id": s.get("id"),
        "title": s.get("title"),
        "units": s.get("units"),
        "frequency": s.get("frequency"),
        "seasonal_adjustment": s.get("seasonal_adjustment"),
    }


def build_macro_table(rows):
    """Tidy/long rows → an Arrow table with the fixed silver schema (series_id:str, date:date32, value:f64).

    Explicit column types (not inferred) so an all-null value column or an empty run still produces the
    canonical schema the store loaders and the TimescaleDB hypertable expect — the time axis column
    (``date``) is always present, which is the FINANCE timescale invariant the tests assert.
    """
    series_ids = [r.get("series_id") for r in rows]
    dates = [r.get("date") for r in rows]
    values = [r.get("value") for r in rows]
    return pa.table({
        "series_id": pa.array(series_ids, type=pa.string()),
        "date": pa.array(dates, type=pa.date32()),
        "value": pa.array(values, type=pa.float64()),
    })


def build_meta_table(metas):
    """Series-metadata dicts → the fred_series_meta dim Arrow table (all string columns)."""
    cols = {c: pa.array([m.get(c) for m in metas], type=pa.string()) for c in META_COLUMNS}
    return pa.table(cols)
