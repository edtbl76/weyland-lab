"""Tests for the dagster-free ``land_core`` (B158 follow-up B).

``land_core`` is the pure heart of the land-asset factory: it decides WHAT gets written (each
``{name: arrow_table}`` to ``<name>/<name>.parquet``) and WHEN a land fails closed (zero rows across
every table). No dagster and no minio at module scope, so — like every ``*_parse`` leaf — it verifies
independent of the runtime. The ``put`` callback is injected so the write path is exercised against a
recorder rather than a real object store.
"""
import io

import pyarrow as pa
import pyarrow.parquet as pq


def _tbl(n=3):
    return pa.table({"x": list(range(n))})


def test_total_rows_sums_across_tables(land_core):
    assert land_core.total_rows({"a": _tbl(3), "b": _tbl(2)}) == 5


def test_total_rows_empty_map_is_zero(land_core):
    assert land_core.total_rows({}) == 0


def test_total_rows_all_empty_tables_is_zero(land_core):
    # THE fail-closed trigger: tables present but every one carries zero rows. The factory raises on
    # this, so it must read as 0 — the same "an empty result is not a successful one" rule the guards use.
    assert land_core.total_rows({"a": _tbl(0), "b": _tbl(0)}) == 0


def test_write_tables_puts_each_at_name_slash_name_parquet(land_core):
    puts = []

    def put(key, data):
        puts.append((key, data))

    written = land_core.write_tables(put, {"fred_macro": _tbl(4), "fred_series_meta": _tbl(1)})
    keys = [k for k, _ in puts]
    assert keys == ["fred_macro/fred_macro.parquet", "fred_series_meta/fred_series_meta.parquet"]
    assert written == {"fred_macro": 4, "fred_series_meta": 1}
    # the bytes handed to put are REAL parquet, not a placeholder
    tbl = pq.read_table(io.BytesIO(puts[0][1]))
    assert tbl.num_rows == 4


def test_write_tables_empty_map_writes_nothing(land_core):
    puts = []
    written = land_core.write_tables(lambda k, d: puts.append(k), {})
    assert puts == []
    assert written == {}
