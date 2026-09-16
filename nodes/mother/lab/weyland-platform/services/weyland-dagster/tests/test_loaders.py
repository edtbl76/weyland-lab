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


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# Store-writer functions (_load_dataset_to_*). Each reads silver parquet from the minio/lakeFS client and
# writes to a store; we drive them with a FakeMC (fixture parquet via pyarrow) + fake store clients that
# RECORD what they're asked to write, then assert the real payload/schema/coercion/counts they produced.
# The SQL loaders (mysql/cockroach/timescale) are intentionally NOT covered here: pandas.to_sql needs a real
# SQLAlchemy engine (not a test dep, and this pass is test-file-only), and TimescaleDB adds Postgres-only
# hypertable DDL — those are validated live against the real databases, not mockable without theater.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
import io as _io               # noqa: E402
import logging                 # noqa: E402

import pyarrow as _pa          # noqa: E402
import pyarrow.parquet as _pq  # noqa: E402

_LOG = logging.getLogger("test_loaders")


class _Obj:
    def __init__(self, name):
        self.object_name = name


class FakeMC:
    """Minimal minio-client stand-in. `files` maps a filename -> list of row dicts; list_objects yields one
    parquet object per file under the requested prefix, and fget_object writes that file's fixture parquet to
    the temp path the loader downloads to."""
    def __init__(self, files):
        self.files = files

    def list_objects(self, repo, prefix, recursive=True):
        return [_Obj(prefix + fn) for fn in self.files]

    def fget_object(self, repo, name, path):
        rows = self.files[name.split("/")[-1]]
        _pq.write_table(_pa.Table.from_pylist(rows), path)


class _Cfg:
    def __init__(self, repo="repo", domain="health"):
        self.repo = repo
        self.domain = domain


@pytest.fixture
def drivers():
    """Register stub store-driver modules the loaders import at call time (the real drivers aren't test deps).
    Each stub exposes only the surface the loader touches; the cassandra concurrent-writer records its params."""
    import sys
    import types

    added = []
    cass_calls = []

    def _put(name, module):
        sys.modules[name] = module
        added.append(name)

    cassandra = types.ModuleType("cassandra")
    concurrent = types.ModuleType("cassandra.concurrent")

    def _eca(session, prepared, params, concurrency=1):
        cass_calls.extend(list(params))

    concurrent.execute_concurrent_with_args = _eca
    cassandra.concurrent = concurrent
    _put("cassandra", cassandra)
    _put("cassandra.concurrent", concurrent)

    qc = types.ModuleType("qdrant_client")
    qm = types.ModuleType("qdrant_client.models")

    class PointStruct:
        def __init__(self, id, vector, payload):
            self.id, self.vector, self.payload = id, vector, payload

    class VectorParams:
        def __init__(self, size, distance):
            self.size, self.distance = size, distance

    class Distance:
        COSINE = "Cosine"

    qm.PointStruct, qm.VectorParams, qm.Distance = PointStruct, VectorParams, Distance
    qc.models = qm
    _put("qdrant_client", qc)
    _put("qdrant_client.models", qm)

    weaviate = types.ModuleType("weaviate")
    wclasses = types.ModuleType("weaviate.classes")
    wconfig = types.ModuleType("weaviate.classes.config")

    class Property:
        def __init__(self, name, data_type):
            self.name, self.data_type = name, data_type

    class DataType:
        TEXT = "text"

    class _Vec:
        @staticmethod
        def none():
            return "none"

    class Configure:
        Vectorizer = _Vec

    wconfig.Property, wconfig.DataType, wconfig.Configure = Property, DataType, Configure
    wclasses.config = wconfig
    weaviate.classes = wclasses
    _put("weaviate", weaviate)
    _put("weaviate.classes", wclasses)
    _put("weaviate.classes.config", wconfig)

    osp = types.ModuleType("opensearchpy")
    osh = types.ModuleType("opensearchpy.helpers")

    def _bulk(client, actions, chunk_size=None, raise_on_error=False):
        acts = list(actions)
        client._bulk_actions.extend(acts)
        return len(acts), []

    osh.bulk = _bulk
    osp.helpers = osh
    _put("opensearchpy", osp)
    _put("opensearchpy.helpers", osh)

    yield {"cass_calls": cass_calls}
    for name in added:
        sys.modules.pop(name, None)


# ── vector backends (records passed directly — no parquet read) ──────────────────────────────────────
def test_qdrant_upserts_points_with_sequential_ids_and_payload(loaders, drivers):
    class FakeQ:
        def __init__(self):
            self.recreated = None
            self.upserts = []

        def recreate_collection(self, coll, vectors_config):
            self.recreated = (coll, vectors_config)

        def upsert(self, collection_name, points):
            self.upserts.append((collection_name, points))

    client = FakeQ()
    records = [{"vector": [0.1, 0.2], "payload": {"row_id": "a"}},
               {"vector": [0.3, 0.4], "payload": {"row_id": "b"}}]
    n = loaders._load_dataset_to_qdrant(client, 2, records, "coll", _LOG)
    assert n == 2
    assert client.recreated[0] == "coll" and client.recreated[1].size == 2
    pts = client.upserts[0][1]
    assert [p.id for p in pts] == [0, 1]
    assert pts[0].vector == [0.1, 0.2] and pts[0].payload == {"row_id": "a"}


def test_qdrant_batches_upserts_with_continuous_ids(loaders, drivers):
    class FakeQ:
        def __init__(self):
            self.upserts = []

        def recreate_collection(self, coll, vectors_config):
            pass

        def upsert(self, collection_name, points):
            self.upserts.append(points)

    client = FakeQ()
    records = [{"vector": [0.0], "payload": {"row_id": str(i)}} for i in range(1500)]  # > _VEC_UPSERT_BATCH
    n = loaders._load_dataset_to_qdrant(client, 1, records, "coll", _LOG)
    assert n == 1500
    assert len(client.upserts) == 2                       # 1000 + 500
    assert client.upserts[0][0].id == 0 and client.upserts[1][0].id == 1000  # ids continue across batches


def test_weaviate_creates_class_from_payload_keys_and_reports_landed_minus_failed(loaders, drivers):
    class Failed:
        def __init__(self, msg):
            self.message = msg

    class Batch:
        def __init__(self):
            self.added = []
            self.failed_objects = [Failed("boom")]      # 1 object rejected by the dynamic batch

        def dynamic(self):
            outer = self

            class Ctx:
                def __enter__(self):
                    return outer

                def __exit__(self, *a):
                    return False

            return Ctx()

        def add_object(self, properties, vector):
            self.added.append((properties, vector))

    class Col:
        def __init__(self, batch):
            self.batch = batch

    class Collections:
        def __init__(self, col):
            self._col = col
            self.created = None

        def list_all(self):
            return {}                                    # class not present → no delete

        def delete(self, cls):
            pass

        def create(self, name, vectorizer_config, properties):
            self.created = (name, properties)

        def get(self, cls):
            return self._col

    batch = Batch()

    class Client:
        def __init__(self):
            self.collections = Collections(Col(batch))

    client = Client()
    records = [{"vector": [0.1], "payload": {"row_id": "a", "name": "x"}},
               {"vector": [0.2], "payload": {"row_id": "b", "name": "y"}}]
    landed = loaders._load_dataset_to_weaviate(client, 1, records, "Cls", _LOG)
    assert landed == 1                                   # 2 add_object calls - 1 failed = honest landed count
    assert client.collections.created[0] == "Cls"
    assert {p.name for p in client.collections.created[1]} == {"row_id", "name"}
    assert len(batch.added) == 2 and batch.added[0][1] == [0.1]


def test_lancedb_builds_fixed_size_vector_table_and_drops_existing(loaders):
    class Tbl:
        def create_index(self, metric, vector_column_name):
            raise AssertionError("index should not build for a tiny table")

    class DB:
        def __init__(self):
            self.created = None
            self.dropped = []

        def table_names(self):
            return ["tbl"]                               # already exists → must be dropped first

        def drop_table(self, t):
            self.dropped.append(t)

        def create_table(self, name, table):
            self.created = (name, table)
            return Tbl()

    db = DB()
    records = [{"vector": [0.1, 0.2], "payload": {"row_id": "a"}},
               {"vector": [0.3, 0.4], "payload": {"row_id": "b"}}]
    n = loaders._load_dataset_to_lancedb(db, 2, records, "tbl", _LOG)
    assert n == 2
    assert db.dropped == ["tbl"]
    name, table = db.created
    assert name == "tbl" and table.num_rows == 2
    schema = {f.name: str(f.type) for f in table.schema}
    assert "fixed_size_list" in schema["vector"] and "row_id" in schema


# ── stores that read parquet via FakeMC.fget_object ──────────────────────────────────────────────────
def test_mongo_drops_collection_and_inserts_row_docs(loaders):
    inserted, dropped = [], []

    class Coll:
        def __init__(self, name):
            self.name = name

        def drop(self):
            dropped.append(self.name)

        def insert_many(self, docs, ordered=True):
            inserted.extend(docs)

    class DB:
        def __getitem__(self, name):
            return Coll(name)

    class Client:
        def __getitem__(self, dbname):
            return DB()

    loaders.io.branch = lambda: "main"
    mc = FakeMC({"nhanes.parquet": [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]})
    out = loaders._load_dataset_to_mongo(mc, _Cfg(domain="health"), "nhanes", Client(), _LOG)
    assert out == {"nhanes": 2}
    assert dropped == ["nhanes"]                         # idempotent reload: collection dropped first
    assert inserted == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_cassandra_derives_schema_coerces_and_sentinels_null_partition(loaders, drivers):
    executed = []

    class Sess:
        def execute(self, q):
            executed.append(q)

        def prepare(self, q):
            return ("PREPARED", q)

    loaders.io.branch = lambda: "main"
    mc = FakeMC({"who.parquet": [{"country": "US", "val": 1.5},
                                 {"country": "", "val": float("nan")}]})
    out = loaders._load_dataset_to_cassandra(Sess(), mc, _Cfg(domain="health"), "who", "country", _LOG)
    assert out == {"datasets_health.who": 2}

    create = next(q for q in executed if q.startswith("CREATE TABLE"))
    assert "datasets_health.who" in create
    assert '"country" text' in create and '"val" double' in create   # _cql_col dtype mapping
    assert "row_id uuid" in create and 'PRIMARY KEY (("country"), row_id)' in create
    assert any(q.startswith("DROP TABLE IF EXISTS") for q in executed)

    rows = drivers["cass_calls"]                          # tuples: (country, val, uuid)
    assert rows[0][0] == "US" and rows[0][1] == 1.5
    assert rows[1][0] == "__UNKNOWN__" and rows[1][1] is None   # blank partition → sentinel; NaN double → None


def test_neo4j_creates_constraints_clears_and_writes_batches(loaders, drivers):
    run_queries, write_batches = [], []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def run(self, q, **kw):
            run_queries.append(q)

        def execute_write(self, fn, node_q, edge_q, rows):
            class Tx:
                def run(self, q, rows):
                    pass

            fn(Tx(), node_q, edge_q, rows)               # exercise _write_neo4j_batch too
            write_batches.append(list(rows))

    class Driver:
        def session(self):
            return Session()

    loaders.io.branch = lambda: "main"
    spec = {"nodes": [{"label": "Country", "key": "code"}], "edges": []}
    mc = FakeMC({"who.parquet": [{"code": "US"}, {"code": "CA"}]})
    out = loaders._load_dataset_to_neo4j(Driver(), mc, _Cfg(domain="health"), "who", spec, _LOG)
    assert out == {"who": 2}
    assert any("CREATE CONSTRAINT" in q and "`Country`" in q for q in run_queries)
    assert any("DETACH DELETE" in q for q in run_queries)          # clean rebuild
    assert write_batches and write_batches[0] == [{"code": "US"}, {"code": "CA"}]


def test_neo4j_parses_list_columns_for_list_edges(loaders, drivers):
    written = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def run(self, q, **kw):
            pass

        def execute_write(self, fn, node_q, edge_q, rows):
            written.extend(rows)

    class Driver:
        def session(self):
            return Session()

    loaders.io.branch = lambda: "main"
    # a dst_list edge → the dst column must be parsed from a stringified list into a real list before write
    # dst_list_key is the FIELD NAME to pull from each dict element (loaders passes it as _parse_list(key=...)),
    # not a bool — the loader coerces the extracted numeric-string id to int to match int-keyed :Genre nodes.
    spec = {"nodes": [{"label": "Track", "key": "tid"}],
            "edges": [{"rel": "HAS_GENRE", "src": ("Track", "tid", "tid"),
                       "dst": ("Genre", "gid", "genres"), "dst_list": True, "dst_list_key": "genre_id"}]}
    mc = FakeMC({"t.parquet": [{"tid": "1", "genres": "[{'genre_id': '21'}]"}]})
    loaders._load_dataset_to_neo4j(Driver(), mc, _Cfg(domain="music"), "fma", spec, _LOG)
    assert written[0]["genres"] == [21]                  # _parse_list applied with the dst_list_key


def test_opensearch_recreates_index_and_bulks_row_docs(loaders, drivers):
    class Indices:
        def __init__(self):
            self.deleted, self.refreshed = [], []

        def delete(self, index, ignore=None):
            self.deleted.append(index)

        def refresh(self, index):
            self.refreshed.append(index)

    class Client:
        def __init__(self):
            self.indices = Indices()
            self._bulk_actions = []

    loaders.io.branch = lambda: "main"
    client = Client()
    mc = FakeMC({"who.parquet": [{"a": 1}, {"a": 2}]})
    out = loaders._load_dataset_to_opensearch(client, mc, _Cfg(domain="health"), "who", _LOG)
    assert out == {"who": 2}
    assert client.indices.deleted == ["who"] and client.indices.refreshed == ["who"]
    assert client._bulk_actions[0] == {"_index": "who", "_source": {"a": 1}}


def test_clickhouse_native_s3_ingest_builds_mergetree_and_counts(loaders, monkeypatch):
    commands = []

    class Client:
        def command(self, sql, parameters=None):
            commands.append((sql, parameters))
            return 5 if sql.startswith("SELECT count()") else None

    loaders.io.branch = lambda: "main"
    loaders.io.endpoint = lambda: "http://lakefs:8000"
    monkeypatch.setenv("LAKEFS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("LAKEFS_SECRET_ACCESS_KEY", "s")
    mc = FakeMC({"who.parquet": []})                     # clickhouse reads server-side via s3(); no parquet fetch
    out = loaders._load_dataset_to_clickhouse(Client(), mc, _Cfg(repo="repo", domain="health"), "who", _LOG)
    assert out == {"datasets_health.who": 5}
    create = next(s for s, _ in commands if s.startswith("CREATE TABLE"))
    assert "MergeTree" in create and "s3(" in create
    assert any(s.startswith("DROP TABLE IF EXISTS") and "`datasets_health`.`who`" in s for s, _ in commands)
    # lakeFS creds are passed as bound params, never interpolated into the SQL text
    create_params = next(p for s, p in commands if s.startswith("CREATE TABLE"))
    assert create_params["k"] == "k" and create_params["url"].endswith("/repo/main/parquet/who/who.parquet")


# ── wave 2: the SQL store-writers, driven against a real in-memory sqlite engine ──────────────────────
# _load_dataset_to_mysql / _cockroach use pandas.to_sql(engine); we point engine_for at sqlite and READ THE
# ROWS BACK — a genuine write-path assertion, not a mock. (_timescale is NOT covered: its create_hypertable
# DDL is Postgres-only and errors on sqlite → it needs a Postgres testcontainer, validated live instead.)
import sqlalchemy as _sa  # noqa: E402


def _parquet_bytes(rows):
    buf = _io.BytesIO()
    _pq.write_table(_pa.Table.from_pylist(rows), buf)
    return buf.getvalue()


def test_load_dataset_to_mysql_writes_rows_read_back(loaders, monkeypatch):
    rows = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    monkeypatch.setattr(loaders, "_mysql_ensure_database", lambda dataset, log: None)   # no live CREATE DATABASE
    monkeypatch.setattr(loaders.io, "branch", lambda: "main", raising=False)
    monkeypatch.setattr(loaders.io, "fetch", lambda mc, repo, name: _parquet_bytes(rows), raising=False)
    eng = _sa.create_engine("sqlite://")
    out = loaders._load_dataset_to_mysql(FakeMC({"people.parquet": rows}), _Cfg(), "demo", lambda ds: eng, _LOG)
    assert out == {"demo.people": 2}
    with eng.connect() as c:
        assert c.execute(_sa.text("SELECT id, name FROM people ORDER BY id")).fetchall() == [(1, "a"), (2, "b")]


class _FakeServerEngine:
    """Stands in for the CockroachDB `defaultdb` server engine — its only job is to accept the `CREATE DATABASE`
    (sqlite has no such statement), recording nothing else."""
    def connect(self):
        class _Conn:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def execute(self_, *a, **k):
                return None

            def commit(self_):
                pass
        return _Conn()


def test_load_dataset_to_cockroach_writes_rows_read_back(loaders, monkeypatch):
    rows = [{"id": 1, "v": 10}, {"id": 2, "v": 20}]
    monkeypatch.setattr(loaders.io, "branch", lambda: "main", raising=False)
    eng = _sa.create_engine("sqlite://")
    out = loaders._load_dataset_to_cockroach(
        FakeMC({"nums.parquet": rows}), _Cfg(), "demo",
        lambda ds: _FakeServerEngine() if ds == "defaultdb" else eng, _LOG)
    assert out == {"demo.nums": 2}
    with eng.connect() as c:
        assert c.execute(_sa.text("SELECT count(*) FROM nums")).scalar() == 2
