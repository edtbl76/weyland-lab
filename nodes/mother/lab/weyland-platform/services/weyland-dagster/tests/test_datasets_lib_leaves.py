"""Tests for the pure ``datasets_lib`` leaf helpers that run on EVERY dataset load: column sanitization, null-type
coercion, format dispatch, Iceberg identifier derivation, and the per-domain config. These are silent-corruption
risks — a bad column rename or a colliding table id loses data quietly — so each asserts the real output.

These modules use relative imports (``from . import io``) + reach the readers sibling, so — like loaders — they
can't be loaded by ``conftest.load_isolated`` (which bypasses the package). Instead this file registers a synthetic
``weyland_pipeline.assets.datasets_lib`` package pointing at the real dir (so ``from .readers import ...`` resolves)
and stubs the minio-backed ``io`` sibling the pure functions never touch. Module-scope so it runs at collection,
before any fixture; we hold direct references to the imported modules, so later fixture teardown can't disturb them.
"""
import importlib
import json
import os
import sys
import types

import pyarrow as pa
import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # weyland-dagster/
_PKG = "weyland_pipeline.assets.datasets_lib"
_DL_DIR = os.path.join(_ROOT, "weyland_pipeline", "assets", "datasets_lib")

for _name in ("weyland_pipeline", "weyland_pipeline.assets"):
    if _name not in sys.modules:
        _m = types.ModuleType(_name); _m.__path__ = []; sys.modules[_name] = _m
if _PKG not in sys.modules:
    _dl = types.ModuleType(_PKG); _dl.__path__ = [_DL_DIR]; sys.modules[_PKG] = _dl
if _PKG + ".io" not in sys.modules:                                          # minio-backed; untouched by pure fns
    _io_stub = types.ModuleType(_PKG + ".io"); _io_stub.branch = lambda: "main"
    sys.modules[_PKG + ".io"] = _io_stub

readers = importlib.import_module(_PKG + ".readers")
writers = importlib.import_module(_PKG + ".writers")
config = importlib.import_module(_PKG + ".config")


class _Log:
    def __init__(self):
        self.warnings, self.errors = [], []

    def warning(self, m):
        self.warnings.append(m)

    def error(self, m):
        self.errors.append(m)


# ── readers.sanitize_columns ─────────────────────────────────────────────────────────────────────────
def test_sanitize_columns_fixes_empty_digit_and_invalid_chars():
    t = pa.Table.from_arrays([pa.array([1]), pa.array([2]), pa.array([3]), pa.array([4])],
                             names=["", "1col", "a.b", "ok"])
    out = readers.sanitize_columns(t)
    # ""→column_0 (blank), "1col"→col_1col (digit-leading guard), "a.b"→a_b (invalid char), "ok" unchanged
    assert out.column_names == ["column_0", "col_1col", "a_b", "ok"]


def test_sanitize_columns_dedups_collisions_introduced_by_normalization():
    t = pa.Table.from_arrays([pa.array([1]), pa.array([2])], names=["a.b", "a_b"])  # both → a_b
    out = readers.sanitize_columns(t)
    assert out.column_names == ["a_b", "a_b_1"]


def test_sanitize_columns_noop_when_already_clean():
    t = pa.table({"a": [1], "b": [2]})
    assert readers.sanitize_columns(t) is t          # rename only when needed


# ── readers.coerce_null_cols ─────────────────────────────────────────────────────────────────────────
def test_coerce_null_cols_casts_all_null_column_to_string():
    t = pa.Table.from_arrays([pa.array([None, None], type=pa.null()), pa.array([1, 2])], names=["x", "y"])
    out = readers.coerce_null_cols(t)
    assert out.schema.field("x").type == pa.string()   # null-typed → string (Iceberg-writable)
    assert out.schema.field("y").type == pa.int64()     # real type untouched


def test_coerce_null_cols_noop_when_no_null_type():
    t = pa.table({"a": [1]})
    assert readers.coerce_null_cols(t) is t


# ── readers.read_to_table (format dispatch) ──────────────────────────────────────────────────────────
def test_read_to_table_csv():
    t = readers.read_to_table("raw/x.csv", b"a,b\n1,2\n3,4\n", _Log())
    assert t.num_rows == 2 and t.column_names == ["a", "b"]


def test_read_to_table_json_top_level_list():
    t = readers.read_to_table("x.json", json.dumps([{"a": 1}, {"a": 2}]).encode(), _Log())
    assert t.num_rows == 2


def test_read_to_table_json_dict_value_key():
    t = readers.read_to_table("x.JSON", json.dumps({"value": [{"a": 1}]}).encode(), _Log())
    assert t.num_rows == 1                              # case-insensitive extension + dict "value" record list


def test_read_to_table_json_empty_record_list_skips():
    log = _Log()
    assert readers.read_to_table("x.json", json.dumps({"nope": 5}).encode(), log) is None
    assert log.warnings


def test_read_to_table_unsupported_extension_returns_none_and_warns():
    log = _Log()
    assert readers.read_to_table("x.txt", b"hi", log) is None
    assert log.warnings


def test_read_to_table_unreadable_data_returns_none_and_logs_error():
    log = _Log()
    assert readers.read_to_table("x.json", b"{not valid json", log) is None
    assert log.errors                                   # one bad source must not raise, just skip+log


# ── writers.ice_ident (per-file Iceberg table id) ────────────────────────────────────────────────────
def test_ice_ident_single_file_folder_uses_table_name():
    assert writers.ice_ident("usda", "usda") == "usda"


def test_ice_ident_multi_file_combines_and_sanitizes():
    # name != table → table_name, non-alnum runs → single _, lowercased (so 30 CSVs don't overwrite one table)
    assert writers.ice_ident("audioset", "train-set") == "audioset_train_set"


def test_ice_ident_digit_leading_gets_t_prefix():
    assert writers.ice_ident("123", "456") == "t_123_456"


# ── config.DomainConfig ──────────────────────────────────────────────────────────────────────────────
def test_domain_config_producer_and_empty_allowlist_defaults():
    c = config.DomainConfig(domain="music", repo="r", namespace="datasets_music", group_name="g")
    assert c.producer == "datasets_music"
    assert c.parquet_allow == frozenset() and c.mysql_allow == frozenset()
    assert c.timescale_allow == {} and c.neo4j_allow == {} and c.vector_allow == {}


def test_domain_config_is_frozen():
    import dataclasses
    c = config.DomainConfig(domain="health", repo="r", namespace="n", group_name="g")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.domain = "x"
