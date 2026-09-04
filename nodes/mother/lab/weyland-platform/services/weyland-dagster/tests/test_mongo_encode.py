"""Tests for the dagster-free ``mongo_encode.to_bson_encodable`` helper (B113 Phase 2).

The MongoDB store loader decodes each silver Parquet batch with ``RecordBatch.to_pylist()`` and hands the
dicts to ``insert_many``. Arrow ``date32``/``date64`` columns decode to python ``datetime.date``, which BSON
CANNOT encode — PyMongo raises "cannot encode object". EDGAR's company_financials/company_filings carry real
date columns (period_end, filed, report_date), so the whole finance→Mongo fan-out failed. FRED-only domains
never tripped it because they have no date columns. This helper casts date columns to microsecond timestamps
so ``to_pylist()`` yields ``datetime.datetime`` (BSON-encodable) — verified independent of the dagster runtime.
"""
import datetime


def test_date_column_becomes_datetime(mongo_encode):
    import pyarrow as pa

    batch = pa.record_batch(
        [pa.array([datetime.date(2024, 9, 30), datetime.date(2023, 9, 30)], type=pa.date32())],
        names=["period_end"],
    )
    docs = mongo_encode.to_bson_encodable(batch).to_pylist()
    # BSON needs datetime.datetime, not datetime.date — and datetime IS a subclass of date, so check exact type.
    assert type(docs[0]["period_end"]) is datetime.datetime
    assert docs[0]["period_end"] == datetime.datetime(2024, 9, 30, 0, 0, 0)
    assert docs[1]["period_end"].date() == datetime.date(2023, 9, 30)


def test_non_date_columns_pass_through_untouched(mongo_encode):
    import pyarrow as pa

    batch = pa.record_batch(
        [pa.array([320085, None], type=pa.int64()), pa.array([1.5, None], type=pa.float64()),
         pa.array(["AAPL", "MSFT"], type=pa.string())],
        names=["cik", "value", "ticker"],
    )
    docs = mongo_encode.to_bson_encodable(batch).to_pylist()
    assert docs[0] == {"cik": 320085, "value": 1.5, "ticker": "AAPL"}
    assert docs[1]["cik"] is None and docs[1]["value"] is None  # nulls preserved, not coerced


def test_null_dates_stay_none(mongo_encode):
    import pyarrow as pa

    batch = pa.record_batch(
        [pa.array([datetime.date(2024, 1, 1), None], type=pa.date32())], names=["filed"])
    docs = mongo_encode.to_bson_encodable(batch).to_pylist()
    assert docs[1]["filed"] is None
    assert type(docs[0]["filed"]) is datetime.datetime


def test_batch_with_no_dates_is_returned_as_is(mongo_encode):
    import pyarrow as pa

    batch = pa.record_batch([pa.array([1, 2], type=pa.int64())], names=["n"])
    out = mongo_encode.to_bson_encodable(batch)
    assert out.to_pylist() == [{"n": 1}, {"n": 2}]


def test_mixed_date_and_value_row_is_fully_encodable(mongo_encode):
    # The exact shape that broke finance: a company_financials row with a date AND a numeric value.
    import pytest
    bson = pytest.importorskip("bson")  # pymongo's bson; skip cleanly in the light lane (live insert is the real proof)
    import pyarrow as pa

    batch = pa.record_batch(
        [pa.array([320085], type=pa.int64()),
         pa.array([datetime.date(2024, 9, 28)], type=pa.date32()),
         pa.array([391035000000.0], type=pa.float64())],
        names=["cik", "period_end", "value"],
    )
    doc = mongo_encode.to_bson_encodable(batch).to_pylist()[0]
    # The real proof: BSON actually encodes it (this raised before the fix).
    bson.encode(doc)
