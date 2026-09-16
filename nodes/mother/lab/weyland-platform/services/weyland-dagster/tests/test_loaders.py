"""Tests for the pure helpers in ``datasets_lib/loaders`` — the store-load logic that runs on EVERY dataset.

Three classes of risk, all silent if wrong:
  1. **Identifier safety** — db/keyspace/table/label names come from dataset config and are INTERPOLATED into SQL/
     CQL/Cypher (identifiers can't be bound as params). A bad name must be rejected or safely quoted, or it's an
     injection / a broken statement. (_safe_ident / _q / _sql_ident / _bt)
  2. **Multi-value parsing** — `_parse_list` turns a stringified cell ("[{'genre_id':'21'}]") into real list
     elements and coerces numeric ids to int so they MATCH int-keyed graph nodes. Get it wrong and edges silently
     point nowhere (radiohead → genre 21 vs "21").
  3. **Cypher compilation** — `_neo4j_queries` compiles a GraphSpec into constraint/node/edge Cypher. Wrong shape =
     duplicated nodes, O(degree) supernode writes, or edges that match nothing.

The store-write functions themselves (`_load_dataset_to_*`) are validated live against the real stores; these cover
the decision logic they all depend on, with no dagster/minio/live-store runtime.
"""
import datetime

import pytest


# ── identifier safety ──────────────────────────────────────────────────────────────────────────────
def test_safe_ident_allows_snake_case(loaders):
    assert loaders._safe_ident("open_food_facts") == "open_food_facts"
    assert loaders._safe_ident("t123") == "t123"


@pytest.mark.parametrize("bad", ['a"b', "a;b", "a b", "a-b", "drop table x", "", 'x") OR 1=1--'])
def test_safe_ident_rejects_injection_shaped_names(loaders, bad):
    with pytest.raises(ValueError):
        loaders._safe_ident(bad)


def test_q_doubles_embedded_double_quotes(loaders):
    assert loaders._q('col"name') == 'col""name'          # closes the "..." identifier safely
    assert loaders._q("plain") == "plain"


def test_sql_ident_sanitizes_and_guards_digit_leading(loaders):
    assert loaders._sql_ident("Open Food Facts!") == "open_food_facts"
    assert loaders._sql_ident("123abc") == "t_123abc"     # a bare digit-leading ident is invalid in MySQL
    assert loaders._sql_ident("--weird--") == "weird"


def test_bt_backtick_quotes_and_escapes(loaders):
    assert loaders._bt("Genre") == "`Genre`"
    assert loaders._bt("a`b") == "`a``b`"                  # a stray backtick can't break out of the quoting


# ── multi-value parsing ────────────────────────────────────────────────────────────────────────────
def test_parse_list_none_and_empty(loaders):
    assert loaders._parse_list(None) == []
    assert loaders._parse_list("") == []
    assert loaders._parse_list("   ") == []


def test_parse_list_real_sequence(loaders):
    assert loaders._parse_list(["a", "b"]) == ["a", "b"]
    assert loaders._parse_list(("x", 2)) == ["x", "2"]     # stringified for the scalar-list path


def test_parse_list_stringified_preserves_commas_inside_elements(loaders):
    # ast.literal_eval keeps the comma INSIDE "Inside, small room" — a naive split would make 3 elements
    out = loaders._parse_list("['Speech', 'Inside, small room']")
    assert out == ["Speech", "Inside, small room"]


def test_parse_list_extracts_dict_key_and_coerces_numeric_ids_to_int(loaders):
    # fma track_genres: numeric-string ids must become int to MATCH the int-keyed :Genre nodes
    out = loaders._parse_list("[{'genre_id': '21'}, {'genre_id': '38'}]", key="genre_id")
    assert out == [21, 38]
    assert all(isinstance(x, int) for x in out)


def test_parse_list_unparseable_with_key_yields_empty_not_garbage(loaders):
    assert loaders._parse_list("not a list literal", key="genre_id") == []


def test_parse_list_unparseable_without_key_falls_back_to_comma_split(loaders):
    assert loaders._parse_list("rock, pop, jazz") == ["rock", "pop", "jazz"]


# ── Cypher compilation ─────────────────────────────────────────────────────────────────────────────
def test_neo4j_queries_emits_unique_constraint_per_node(loaders):
    spec = {"nodes": [{"label": "Genre", "key": "genre_id"}]}
    constraints, node_q, edge_q = loaders._neo4j_queries(spec)
    assert any("CREATE CONSTRAINT" in c and "`Genre`" in c and "IS UNIQUE" in c for c in constraints)
    assert len(node_q) == 1 and "MERGE (n:`Genre`" in node_q[0] and "UNWIND $rows" in node_q[0]
    assert edge_q == []


def test_neo4j_queries_dedups_constraints_across_node_and_edge_endpoints(loaders):
    spec = {
        "nodes": [{"label": "Track", "key": "tid"}, {"label": "Genre", "key": "gid"}],
        "edges": [{"rel": "HAS_GENRE", "src": ("Track", "tid", "tid"), "dst": ("Genre", "gid", "gid")}],
    }
    constraints, _n, edge_q = loaders._neo4j_queries(spec)
    # Track + Genre each appear as a node AND an edge endpoint, but the constraint is emitted once each.
    assert sum("`Track`" in c for c in constraints) == 1
    assert sum("`Genre`" in c for c in constraints) == 1
    assert "MATCH (a:`Track`" in edge_q[0] and "CREATE (a)-[r:`HAS_GENRE`]->(b)" in edge_q[0]


def test_neo4j_queries_node_props_become_set_clause(loaders):
    spec = {"nodes": [{"label": "Track", "key": "tid", "props": ["title", "year"]}]}
    _c, node_q, _e = loaders._neo4j_queries(spec)
    assert "SET n.`title` = row.`title`, n.`year` = row.`year`" in node_q[0]


def test_neo4j_queries_dst_list_key_keeps_key_type_no_tostring(loaders):
    # track_genres → genre_id: the dst list carries the real (int) key, so it must NOT be toString'd
    spec = {"edges": [{"rel": "HAS_GENRE", "src": ("Track", "tid", "tid"),
                       "dst": ("Genre", "gid", "genres"), "dst_list": True, "dst_list_key": True}]}
    _c, _n, edge_q = loaders._neo4j_queries(spec)
    q = edge_q[0]
    assert "UNWIND row.`genres` AS _dv" in q and "MERGE (b:`Genre` {`gid`: _dv})" in q
    assert "toString(_dv)" not in q                        # int key preserved


def test_neo4j_queries_scalar_dst_list_is_tostring_trimmed_and_guarded(loaders):
    spec = {"edges": [{"rel": "TAGGED", "src": ("Clip", "cid", "cid"),
                       "dst": ("Label", "name", "labels"), "dst_list": True}]}
    _c, _n, edge_q = loaders._neo4j_queries(spec)
    q = edge_q[0]
    assert "trim(toString(_raw))" in q and "size(_dv) <=" in q   # scalar labels are normalized + length-guarded


def test_neo4j_queries_edge_props_become_relationship_set(loaders):
    spec = {"edges": [{"rel": "RATED", "src": ("User", "uid", "uid"), "dst": ("Movie", "mid", "mid"),
                       "props": ["stars"]}]}
    _c, _n, edge_q = loaders._neo4j_queries(spec)
    assert "SET r.`stars` = row.`stars`" in edge_q[0]


# ── dtype → CQL mapping (uses real pandas, a declared test dep) ───────────────────────────────────────
def test_cql_col_maps_dtypes_and_nan_becomes_none(loaders):
    import numpy as np
    import pandas as pd

    t_int, cast_int = loaders._cql_col(pd.Series([1, 2]).dtype)
    assert t_int == "bigint" and cast_int(np.int64(5)) == 5 and cast_int(np.nan) is None

    t_float, cast_float = loaders._cql_col(pd.Series([1.0, 2.5]).dtype)
    assert t_float == "double" and cast_float(2.5) == 2.5 and cast_float(np.nan) is None

    t_bool, _ = loaders._cql_col(pd.Series([True, False]).dtype)
    assert t_bool == "boolean"

    t_txt, cast_txt = loaders._cql_col(pd.Series(["a", "b"]).dtype)
    assert t_txt == "text" and cast_txt("x") == "x" and cast_txt(None) is None


def test_weaviate_class_is_camelcased_from_domain_and_dataset(loaders):
    assert loaders._weaviate_class("music", "fma_tracks") == "DatasetsMusicFmaTracks"
