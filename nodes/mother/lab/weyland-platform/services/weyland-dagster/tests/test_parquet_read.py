"""Tests for weyland-dagster's dagster-free ``parquet_read`` leaf module (B78, EMA-69).

Loaded in isolation via the ``parquet_read`` fixture, proving both the harness and that the fast lane
never imports the dagster runtime. ``needed_columns`` is the projection the read pulls; ``read_capped``
is the bounded read that replaces the whole-file ``pd.read_parquet`` (loaders.py) that OOMs on OFF's
4.5M × 211 file; ``resolve_text_columns`` is the fail-closed guard for the silent-empty-vector bug that
step 1 proved is real (a column copied from stale field docs would embed nothing and report success).
"""
import os
import tempfile

import pytest


def _write_parquet(columns):
    """Write a tiny parquet from {col: [values]} and return its path (caller unlinks)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    fd, path = tempfile.mkstemp(suffix=".parquet")
    os.close(fd)
    pq.write_table(pa.table(columns), path)
    return path


def test_needed_columns_unions_every_referenced_field(parquet_read):
    # The OFF spec confirmed in step 1: text = product_name+brands+categories_en, filter product_name,
    # id code, payload product_name+brands+url.
    spec = {
        "text": ["product_name", "brands", "categories_en"],
        "filter": "product_name",
        "id": "code",
        "payload": ["product_name", "brands", "url"],
    }
    cols = parquet_read.needed_columns(spec)
    for referenced in ("product_name", "brands", "categories_en", "code", "url"):
        assert referenced in cols, f"{referenced} must be projected"
    # product_name appears in text, filter AND payload — it must be projected exactly once.
    assert cols.count("product_name") == 1
    assert len(cols) == len(set(cols)), "projection must be de-duplicated"


def test_needed_columns_preserves_first_seen_order(parquet_read):
    spec = {"text": ["b", "a"], "id": "c", "payload": ["a", "d"]}
    # b, a (text) → c (id) → d (payload; a already seen)
    assert parquet_read.needed_columns(spec) == ["b", "a", "c", "d"]


def test_needed_columns_empty_spec_projects_nothing(parquet_read):
    assert parquet_read.needed_columns({}) == []


def test_needed_columns_ignores_absent_and_empty_keys(parquet_read):
    assert parquet_read.needed_columns({"text": [], "payload": None, "id": ""}) == []


# --- read_capped: the bounded read that replaces the whole-file pd.read_parquet -------------------

def test_read_capped_materialises_only_the_requested_columns(parquet_read):
    # The core of the OOM fix: given a WIDE file, the read must pull only the projected columns, never
    # the other 200. Proven by the returned frame carrying exactly the requested columns.
    cols = {f"c{i}": [str(i)] * 5 for i in range(50)}
    path = _write_parquet(cols)
    try:
        df = parquet_read.read_capped(path, ["c3", "c41"])
        assert list(df.columns) == ["c3", "c41"]
        assert len(df) == 5
    finally:
        os.unlink(path)


def test_read_capped_stops_at_cap_across_batches(parquet_read):
    path = _write_parquet({"a": [str(i) for i in range(100)]})
    try:
        df = parquet_read.read_capped(path, ["a"], cap=10, batch_size=7)
        assert len(df) == 10  # capped mid-stream, not the full 100
    finally:
        os.unlink(path)


def test_read_capped_drops_rows_with_an_empty_filter_column(parquet_read):
    # na_filter=False at ingest means "missing" is the empty string, not null — filter on that.
    path = _write_parquet({"name": ["a", "", "b", ""], "x": ["1", "2", "3", "4"]})
    try:
        df = parquet_read.read_capped(path, ["name", "x"], filter_col="name")
        assert list(df["name"]) == ["a", "b"]
        assert list(df["x"]) == ["1", "3"]
    finally:
        os.unlink(path)


def test_read_capped_fails_closed_when_the_filter_column_is_absent(parquet_read):
    # A missing filter column must RAISE, naming it — not silently pass every row (which is how the
    # old code would have shipped an unfiltered, wrong-sized collection).
    path = _write_parquet({"name": ["a"], "x": ["1"]})
    try:
        with pytest.raises(ValueError, match="filter"):
            parquet_read.read_capped(path, ["name"], filter_col="does_not_exist")
    finally:
        os.unlink(path)


def test_read_capped_projects_only_columns_that_exist(parquet_read):
    # A requested column absent from the file is dropped from the projection (the caller's
    # resolve_text_columns is what turns an all-absent TEXT spec into a hard failure).
    path = _write_parquet({"a": ["1"], "b": ["2"]})
    try:
        df = parquet_read.read_capped(path, ["a", "ghost"])
        assert list(df.columns) == ["a"]
    finally:
        os.unlink(path)


# --- resolve_text_columns: the fail-closed guard for the silent-empty-vector bug ------------------

def test_resolve_text_columns_returns_the_present_ones_in_order(parquet_read):
    assert parquet_read.resolve_text_columns(["b", "a", "z"], {"a", "b", "c"}) == ["b", "a"]


def test_resolve_text_columns_raises_when_every_column_is_absent(parquet_read):
    # Step 1's finding in code form: a text spec whose columns are all missing (the categories_fr
    # mistake) must RAISE, not embed empty strings and report success.
    with pytest.raises(ValueError, match="absent"):
        parquet_read.resolve_text_columns(["categories_fr"], {"product_name", "categories_en"})


# --- build_records: assembling store records (extracted from _build_vectors for coverage) ---------

def _df(columns):
    import pandas as pd

    return pd.DataFrame(columns)


def test_build_records_keys_on_the_spec_id_column_when_present(parquet_read):
    df = _df({"code": ["a", "b"], "brands": ["x", "y"]})
    recs = parquet_read.build_records(df, {"id": "code", "payload": ["brands"]}, [[0.1], [0.2]])
    assert [r["id"] for r in recs] == ["a", "b"]
    assert recs[0] == {"id": "a", "vector": [0.1], "payload": {"row_id": "a", "brands": "x"}}


def test_build_records_falls_back_to_the_row_index_without_an_id_column(parquet_read):
    df = _df({"x": ["p", "q", "r"]})
    recs = parquet_read.build_records(df, {}, [[1], [2], [3]])
    assert [r["id"] for r in recs] == ["0", "1", "2"]
    assert recs[1]["payload"] == {"row_id": "1"}  # row_id is always injected


def test_build_records_stringifies_payload_and_blanks_nulls(parquet_read):
    df = _df({"code": ["a"], "n": [None], "k": [5]})
    recs = parquet_read.build_records(df, {"id": "code", "payload": ["n", "k"]}, [[0.0]])
    assert recs[0]["payload"] == {"row_id": "a", "n": "", "k": "5"}


def test_build_records_ignores_absent_payload_columns(parquet_read):
    df = _df({"code": ["a"]})
    recs = parquet_read.build_records(df, {"id": "code", "payload": ["ghost"]}, [[0.0]])
    assert recs[0]["payload"] == {"row_id": "a"}


# --- vectors_degenerate: the store-side backstop for the empty/identical-vector defect --------------

def test_vectors_degenerate_flags_all_identical(parquet_read):
    assert parquet_read.vectors_degenerate([[1.0, 2.0], [1.0, 2.0], [1.0, 2.0]]) is True


def test_vectors_degenerate_false_when_varied(parquet_read):
    assert parquet_read.vectors_degenerate([[1.0, 2.0], [3.0, 4.0], [1.0, 2.0]]) is False


def test_vectors_degenerate_false_when_too_few_to_judge(parquet_read):
    assert parquet_read.vectors_degenerate([[1.0, 2.0]]) is False
    assert parquet_read.vectors_degenerate([]) is False
