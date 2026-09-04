"""BSON-safe Arrow → document coercion for the MongoDB store loader (B113 Phase 2).

Dagster-free, pyarrow-only, absolute imports — so it loads in the light test lane in isolation (same
contract as ``timeseries.py``/``fred_parse.py``). ``loaders.py`` imports ``to_bson_encodable`` and applies
it to each silver Parquet batch before ``to_pylist()`` → ``insert_many``.

The bug it fixes: BSON has no ``date`` type. Arrow ``date32``/``date64`` columns decode via
``RecordBatch.to_pylist()`` to python ``datetime.date``, which PyMongo REJECTS ("cannot encode object").
EDGAR's company_financials/company_filings carry real date columns (period_end, filed, report_date), so the
finance→Mongo fan-out failed; FRED-only domains never tripped it. Casting date columns to a microsecond
timestamp makes ``to_pylist()`` yield ``datetime.datetime`` (midnight, which BSON accepts) while leaving
every other column — and every null — untouched.
"""
import pyarrow as pa


def to_bson_encodable(batch: pa.RecordBatch) -> pa.RecordBatch:
    """Return ``batch`` with every date column cast to ``timestamp('us')``; a no-op (same object) when the
    batch has no date columns, so non-EDGAR domains pay nothing."""
    date_idx = [i for i, f in enumerate(batch.schema) if pa.types.is_date(f.type)]
    if not date_idx:
        return batch
    cols = list(batch.columns)
    for i in date_idx:
        cols[i] = cols[i].cast(pa.timestamp("us"))
    return pa.RecordBatch.from_arrays(cols, names=batch.schema.names)
