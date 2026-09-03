"""Tests for the dagster-free ``fred_parse`` leaf module (B113 Phase 1, finance domain).

Loaded in isolation via the ``fred_parse`` fixture — proves the fast lane never imports the dagster
runtime. Covers the load-bearing FRED gotcha (``value`` is a STRING; a MISSING observation is the literal
``"."``), the observations→rows shaping, the metadata extraction (fail-closed on an empty payload), and
the FINANCE silver-schema invariant that the TimescaleDB time axis column is always present.

Every fixture below is CAPTURED sample JSON in the exact API shape confirmed live on 2026-09-02 — the
committed tests require NO network and NO FRED_API_KEY.
"""
import datetime

import pytest


# --- captured FRED payloads (verbatim shape from the live API, values abbreviated) ------------------

_META_JSON = {
    "seriess": [
        {
            "id": "UNRATE",
            "title": "Unemployment Rate",
            "units": "Percent",
            "frequency": "Monthly",
            "seasonal_adjustment": "Seasonally Adjusted",
            "observation_start": "1948-01-01",
            "observation_end": "2026-07-01",
            "popularity": 92,
        }
    ]
}

_OBS_JSON = {
    "observations": [
        {"realtime_start": "2026-09-02", "realtime_end": "2026-09-02", "date": "2024-01-01", "value": "3.7"},
        {"realtime_start": "2026-09-02", "realtime_end": "2026-09-02", "date": "2024-02-01", "value": "."},
        {"realtime_start": "2026-09-02", "realtime_end": "2026-09-02", "date": "2024-03-01", "value": "3.9"},
    ],
    "count": 3,
}


# --- parse_fred_value: "." → null, numeric string → float ------------------------------------------

def test_parse_fred_value_missing_dot_is_null(fred_parse):
    # THE gotcha: FRED encodes a missing observation as the literal ".", not null/empty.
    assert fred_parse.parse_fred_value(".") is None


def test_parse_fred_value_numeric_string_becomes_float(fred_parse):
    assert fred_parse.parse_fred_value("4.1") == pytest.approx(4.1)
    assert isinstance(fred_parse.parse_fred_value("4.1"), float)


def test_parse_fred_value_blank_and_none_are_null(fred_parse):
    assert fred_parse.parse_fred_value("") is None
    assert fred_parse.parse_fred_value("   ") is None
    assert fred_parse.parse_fred_value(None) is None


def test_parse_fred_value_handles_negative_and_integer_strings(fred_parse):
    assert fred_parse.parse_fred_value("-0.25") == pytest.approx(-0.25)
    assert fred_parse.parse_fred_value("21538") == pytest.approx(21538.0)


def test_parse_fred_value_unparseable_is_null_not_raise(fred_parse):
    # A non-numeric, non-"." cell must not raise (one bad cell can't sink a series) — it becomes null.
    assert fred_parse.parse_fred_value("N/A") is None


# --- parse_fred_date -------------------------------------------------------------------------------

def test_parse_fred_date_iso_to_date(fred_parse):
    assert fred_parse.parse_fred_date("2024-03-01") == datetime.date(2024, 3, 1)


def test_parse_fred_date_bad_input_is_null(fred_parse):
    assert fred_parse.parse_fred_date("not-a-date") is None
    assert fred_parse.parse_fred_date("") is None
    assert fred_parse.parse_fred_date(None) is None


# --- observations_to_rows: shaping -----------------------------------------------------------------

def test_observations_to_rows_accepts_the_raw_api_dict(fred_parse):
    rows = fred_parse.observations_to_rows("UNRATE", _OBS_JSON)
    assert [r["series_id"] for r in rows] == ["UNRATE", "UNRATE", "UNRATE"]
    assert [r["date"] for r in rows] == [
        datetime.date(2024, 1, 1), datetime.date(2024, 2, 1), datetime.date(2024, 3, 1),
    ]
    # The "." row is KEPT (a real dated gap) with value None; the numeric rows parse to float.
    assert [r["value"] for r in rows] == [pytest.approx(3.7), None, pytest.approx(3.9)]


def test_observations_to_rows_drops_undated_points(fred_parse):
    obs = {"observations": [{"date": "bad", "value": "1.0"}, {"date": "2024-05-01", "value": "2.0"}]}
    rows = fred_parse.observations_to_rows("X", obs)
    assert len(rows) == 1
    assert rows[0]["date"] == datetime.date(2024, 5, 1)


def test_observations_to_rows_empty_yields_nothing(fred_parse):
    assert fred_parse.observations_to_rows("X", {"observations": []}) == []
    assert fred_parse.observations_to_rows("X", {}) == []


# --- extract_series_meta: metadata extraction (fail-closed) ----------------------------------------

def test_extract_series_meta_pulls_the_dim_fields(fred_parse):
    meta = fred_parse.extract_series_meta(_META_JSON)
    assert meta == {
        "series_id": "UNRATE",
        "title": "Unemployment Rate",
        "units": "Percent",
        "frequency": "Monthly",
        "seasonal_adjustment": "Seasonally Adjusted",
    }


def test_extract_series_meta_empty_seriess_fails_closed(fred_parse):
    # A metadata call that returned no series is a real failure, not an empty-but-fine result — must RAISE
    # with a reason naming the empty list, per the lab's silent-failure rule (assert the REASON).
    with pytest.raises(ValueError, match="empty 'seriess'"):
        fred_parse.extract_series_meta({"seriess": []})


def test_extract_series_meta_rejects_non_dict(fred_parse):
    with pytest.raises(ValueError, match="unexpected FRED series metadata type"):
        fred_parse.extract_series_meta(["not", "a", "dict"])


# --- build_macro_table: silver schema + the FINANCE timescale invariant -----------------------------

def test_build_macro_table_has_the_fixed_typed_schema(fred_parse):
    import pyarrow as pa

    rows = fred_parse.observations_to_rows("UNRATE", _OBS_JSON)
    t = fred_parse.build_macro_table(rows)
    assert t.column_names == ["series_id", "date", "value"]
    assert t.schema.field("series_id").type == pa.string()
    assert t.schema.field("date").type == pa.date32()
    assert t.schema.field("value").type == pa.float64()
    assert t.num_rows == 3


def test_build_macro_table_preserves_nulls_from_dot_values(fred_parse):
    rows = fred_parse.observations_to_rows("UNRATE", _OBS_JSON)
    t = fred_parse.build_macro_table(rows)
    assert t.column("value").to_pylist() == [pytest.approx(3.7), None, pytest.approx(3.9)]


def test_build_macro_table_empty_still_yields_the_schema(fred_parse):
    # Explicit types (not inferred) so an empty run still produces the canonical schema the store
    # loaders + the hypertable expect.
    t = fred_parse.build_macro_table([])
    assert t.column_names == ["series_id", "date", "value"]
    assert t.num_rows == 0


def test_finance_timescale_time_col_is_present_in_the_silver_schema(fred_parse):
    # THE invariant: the TimescaleDB hypertable time axis (TIMESCALE_ALLOW["fred_macro"]) must be a real
    # column of the fred_macro silver table — otherwise the hypertable load fails on a missing time column.
    time_col = fred_parse.TIMESCALE_ALLOW[fred_parse.FRED_MACRO]
    assert time_col == "date"
    t = fred_parse.build_macro_table(fred_parse.observations_to_rows("UNRATE", _OBS_JSON))
    assert time_col in t.column_names


def test_finance_allowlists_are_internally_consistent(fred_parse):
    # The config knobs the transform imports: both raw tables present; clickhouse + iceberg cover both;
    # timescale targets exactly the one time-shaped table.
    assert fred_parse.RAW_TABLES == {"fred_macro", "fred_series_meta"}
    assert fred_parse.CLICKHOUSE_ALLOW == {"fred_macro", "fred_series_meta"}
    assert fred_parse.ICEBERG_ALLOW == {"fred_macro", "fred_series_meta"}
    assert set(fred_parse.TIMESCALE_ALLOW) == {"fred_macro"}
    assert len(fred_parse.SERIES_IDS) == 13


# --- build_meta_table ------------------------------------------------------------------------------

def test_build_meta_table_schema_and_values(fred_parse):
    metas = [fred_parse.extract_series_meta(_META_JSON)]
    t = fred_parse.build_meta_table(metas)
    assert t.column_names == ["series_id", "title", "units", "frequency", "seasonal_adjustment"]
    assert t.column("series_id").to_pylist() == ["UNRATE"]
    assert t.column("frequency").to_pylist() == ["Monthly"]
