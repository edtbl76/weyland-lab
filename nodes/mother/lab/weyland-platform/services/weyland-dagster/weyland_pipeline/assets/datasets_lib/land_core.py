"""Dagster-free heart of the land-asset factory (B158 follow-up B).

The land assets across a domain (FRED, EDGAR, market, …) all wrap the same scaffold: skip if fresh,
fetch+shape the source, FAIL CLOSED if it produced nothing, then write each tidy table to
``<repo>/raw/<name>/<name>.parquet``. Only the fetch+shape is genuinely source-specific; this module is
the rest, expressed with no dagster and no minio import so it tests in isolation like the ``*_parse``
leaves. ``landers.build_land_asset`` wraps these in the ``@asset`` + Output boilerplate; the ``put``
callback is injected there (a repo-bound minio put) and stubbed in the tests.
"""
import io as _io

import pyarrow.parquet as pq


def total_rows(tables):
    """Total rows across a ``{name: arrow_table}`` map. Zero — including tables-present-but-all-empty —
    is the factory's fail-closed trigger: a land that shaped no rows must raise, never commit an empty
    raw layer that reads downstream as a successful-but-empty dataset."""
    return sum(t.num_rows for t in tables.values())


def parquet_bytes(table):
    """Serialize one Arrow table to parquet bytes."""
    buf = _io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def write_tables(put, tables):
    """Write each ``{name: arrow_table}`` via ``put(key, data)`` at ``<name>/<name>.parquet``; return
    ``{name: num_rows}``. ``put`` is injected so this stays dagster/minio-free — in the pipeline it is a
    repo-bound minio put, in tests a recorder. Ordering follows the dict, which is insertion-ordered."""
    written = {}
    for name, table in tables.items():
        put(f"{name}/{name}.parquet", parquet_bytes(table))
        written[name] = table.num_rows
    return written
