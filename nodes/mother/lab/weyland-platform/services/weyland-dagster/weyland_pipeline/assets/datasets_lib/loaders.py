"""Store hydration (data-store-mageddon) — the third datasets_lib factory. build_store_load_assets(cfg)
reads silver Parquet from lakeFS and loads it into the Tier-2 stores the grid targets, one loader asset
per store, driven by the explicit per-store allowlists on DomainConfig (a store gets an asset only when
its allowlist is non-empty).

MySQL (always-on, data-mesh ns): dataset → database (pre-created), each parquet file → a table. Written
batched (pyarrow iter_batches → pandas → to_sql append) so big tables (brfss ~3M rows) stay memory-bounded.
"""
import io as _io
import os
import re
import urllib.parse

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from . import io


def _safe_ident(name):
    """B47 hardening: allowlist a bare SQL identifier (db/keyspace/table from dataset config) before it is
    interpolated into a statement — identifiers can't be bound as params. Raises on anything with quotes/
    semicolons/whitespace. Call sites pass config-defined snake_case names, so this never fires in practice."""
    n = str(name)
    if n and all(c.isalnum() or c == "_" for c in n):
        return n
    raise ValueError(f"unsafe SQL identifier: {name!r}")


def _q(name):
    """B47: escape a double-quoted SQL identifier (dataset COLUMN names, which can vary) by doubling quotes."""
    return str(name).replace('"', '""')


_MYSQL_BATCH = 50_000
# Mongo docs are Python dicts (heavy — OFF is 211 all-string cols), so a smaller batch than MySQL's, and
# the parquet is read from a temp FILE (not held in RAM) — the 50k+whole-file approach OOMKilled user-code.
_MONGO_BATCH = 20_000


def _sql_ident(name: str) -> str:
    """A clean MySQL table identifier — non-[A-Za-z0-9_] → _, digit-leading guard."""
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    return s if s and not s[0].isdigit() else f"t_{s}"


def _mysql_engine_factory():
    import sqlalchemy

    host = os.environ.get("MYSQL_HOST", "mysql.data-mesh.svc.cluster.local")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    pw = urllib.parse.quote_plus(os.environ["MYSQL_PASSWORD"])
    cache = {}

    def engine_for(db):
        if db not in cache:
            cache[db] = sqlalchemy.create_engine(f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}")
        return cache[db]

    return engine_for


def _load_dataset_to_mysql(mc, cfg, dataset, engine_for, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in MySQL db <dataset>."""
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        table = _sql_ident(obj.object_name.split("/")[-1][: -len(".parquet")])
        try:
            data = io.fetch(mc, cfg.repo, obj.object_name)
            engine = engine_for(dataset)
            n, first = 0, True
            for batch in pq.ParquetFile(_io.BytesIO(data)).iter_batches(batch_size=_MYSQL_BATCH):
                df = batch.to_pandas()
                # default method (executemany), NOT method="multi": a multi-row INSERT compiles
                # chunksize×columns bind params, which is pathologically slow on wide tables (big_five's
                # 57 cols × 5000 = 285k params hung the compile until the run was killed).
                df.to_sql(table, engine, if_exists="replace" if first else "append",
                          index=False, chunksize=1_000)
                first, n = False, n + len(df)
            out[f"{dataset}.{table}"] = n
            log.info(f"mysql {dataset}.{table}: {n:,} rows")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[f"{dataset}.{table}"] = f"ERROR: {e}"
            log.error(f"mysql {dataset}.{table}: {e}")
    return out


def _tsdb_engine():
    import sqlalchemy

    host = os.environ.get("TIMESCALEDB_HOST", "timescaledb.data-mesh.svc.cluster.local")
    port = os.environ.get("TIMESCALEDB_PORT", "5432")
    db = os.environ.get("TIMESCALEDB_DB", "timeseries")
    user = os.environ.get("TIMESCALEDB_USER", "weyland")
    pw = urllib.parse.quote_plus(os.environ["TIMESCALEDB_PASSWORD"])   # SEC-1: no baked-in fallback
    return sqlalchemy.create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}")


def _load_dataset_to_timescale(mc, cfg, dataset, time_col, engine, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a TimescaleDB hypertable in db `timeseries`,
    partitioned on a derived `ts` timestamptz. WHO GHO's TimeDim is a year → Jan 1 of that year. Rows with
    no usable year are dropped (a hypertable's time column must be non-null). Table name is dataset-prefixed
    (who_gho_<indicator>) since TimescaleDB is one flat db — mirrors the Iceberg/DuckDB per-file naming."""
    import pandas as pd
    import sqlalchemy

    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        table = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        try:
            data = io.fetch(mc, cfg.repo, obj.object_name)
            df = pq.ParquetFile(_io.BytesIO(data)).read().to_pandas()
            if time_col not in df.columns:
                raise KeyError(f"time column {time_col!r} not in {list(df.columns)[:10]}")
            df["ts"] = pd.to_datetime(df[time_col], format="%Y", errors="coerce", utc=True)
            df = df[df["ts"].notna()]
            df.to_sql(table, engine, if_exists="replace", index=False, chunksize=5_000)
            # to_sql made a plain table (dropping any prior hypertable); (re)promote it. migrate_data moves
            # the just-loaded rows into chunks; if_not_exists keeps it idempotent across re-runs.
            with engine.begin() as conn:
                conn.execute(sqlalchemy.text(f"SELECT create_hypertable('{_safe_ident(table)}', 'ts', if_not_exists => TRUE, migrate_data => TRUE)"))  # nosemgrep
            out[table] = int(len(df))
            log.info(f"timescaledb {table}: {len(df):,} rows → hypertable on ts (from {time_col})")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[table] = f"ERROR: {e}"
            log.error(f"timescaledb {table}: {e}")
    return out


def _mongo_client():
    from pymongo import MongoClient

    host = os.environ.get("MONGO_HOST", "mongodb.data-mesh.svc.cluster.local")
    port = os.environ.get("MONGO_PORT", "27017")
    user = urllib.parse.quote_plus(os.environ.get("MONGO_USER", "weyland"))
    pw = urllib.parse.quote_plus(os.environ["MONGO_PASSWORD"])   # SEC-1: no baked-in fallback
    return MongoClient(f"mongodb://{user}:{pw}@{host}:{port}/?authSource=admin")


def _load_dataset_to_mongo(mc, cfg, dataset, client, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a Mongo collection in db datasets_<domain>,
    doc per row. MEMORY-SAFE: the parquet is DOWNLOADED TO A TEMP FILE (not held in RAM — OFF is 1.63GB and
    io.fetch-whole OOMKilled the pod) and read in row batches → insert_many, freeing each batch. Collection
    dropped + reloaded each run (idempotent). Names mirror the per-file convention."""
    import tempfile

    db = client[f"datasets_{cfg.domain}"]
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        coll = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            db[coll].drop()
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk, not RAM
            n = 0
            for batch in pq.ParquetFile(tmp.name).iter_batches(batch_size=_MONGO_BATCH):
                docs = batch.to_pylist()
                if docs:
                    db[coll].insert_many(docs, ordered=False)
                    n += len(docs)
                del batch, docs
            out[coll] = n
            log.info(f"mongo datasets_{cfg.domain}.{coll}: {n:,} docs")
        except Exception as e:  # noqa: BLE001 — per-collection resilience
            out[coll] = f"ERROR: {e}"
            log.error(f"mongo {coll}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


def _cockroach_engine_factory():
    import sqlalchemy

    host = os.environ.get("COCKROACH_HOST", "cockroachdb.data-mesh.svc.cluster.local")
    port = os.environ.get("COCKROACH_PORT", "26257")
    user = os.environ.get("COCKROACH_USER", "root")
    cache = {}

    def engine_for(db):  # cockroachdb dialect (NOT plain postgres — the pg dialect can't parse Cockroach's
        if db not in cache:  # version string). Insecure single-node → user root, no password, sslmode disabled.
            cache[db] = sqlalchemy.create_engine(
                f"cockroachdb://{user}@{host}:{port}/{db}?sslmode=disable")
        return cache[db]

    return engine_for


def _load_dataset_to_cockroach(mc, cfg, dataset, engine_for, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in CockroachDB db <dataset> (created if
    absent). pg-wire, so pandas.to_sql (default executemany, NOT method='multi'). MEMORY-SAFE: parquet
    downloaded to a temp FILE + read in batches (brfss ~3M rows). Table replaced each run (idempotent)."""
    import tempfile
    import sqlalchemy

    with engine_for("defaultdb").connect() as conn:   # CREATE DATABASE from Cockroach's default db
        conn.execute(sqlalchemy.text(f'CREATE DATABASE IF NOT EXISTS "{_safe_ident(dataset)}"'))  # nosemgrep
        conn.commit()
    engine = engine_for(dataset)
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        table = _sql_ident(obj.object_name.split("/")[-1][: -len(".parquet")])
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk
            n, first = 0, True
            for batch in pq.ParquetFile(tmp.name).iter_batches(batch_size=_MYSQL_BATCH):
                df = batch.to_pandas()
                df.to_sql(table, engine, if_exists="replace" if first else "append",
                          index=False, chunksize=1_000)
                first, n = False, n + len(df)
                del batch, df
            out[f"{dataset}.{table}"] = n
            log.info(f"cockroach {dataset}.{table}: {n:,} rows")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[f"{dataset}.{table}"] = f"ERROR: {e}"
            log.error(f"cockroach {dataset}.{table}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


_CQL_BATCH = 5_000


def _cassandra_cluster():
    from cassandra.cluster import Cluster

    hosts = os.environ.get("CASSANDRA_HOSTS", "cassandra.data-mesh.svc.cluster.local").split(",")
    port = int(os.environ.get("CASSANDRA_PORT", "9042"))
    return Cluster(hosts, port=port)


def _cql_col(dtype):
    """Map a pandas dtype → (CQL type, value caster to a Cassandra-safe python native — NaN → None,
    numpy scalars → int/float/str so the driver's type codecs accept them)."""
    import pandas as pd

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean", lambda v: None if pd.isna(v) else bool(v)
    if pd.api.types.is_integer_dtype(dtype):
        return "bigint", lambda v: None if pd.isna(v) else int(v)
    if pd.api.types.is_float_dtype(dtype):
        return "double", lambda v: None if pd.isna(v) else float(v)
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "timestamp", lambda v: None if pd.isna(v) else v.to_pydatetime()
    return "text", lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def _load_dataset_to_cassandra(session, mc, cfg, dataset, partition_raw, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in keyspace datasets_<domain>. Partition
    key = the configured natural column when present in the data (query-first — e.g. who_gho by country);
    otherwise a synthetic row_id (plain dump). A `row_id uuid` clustering column ALWAYS guarantees row
    uniqueness so nothing upserts away on a shared key. MEMORY-SAFE: temp file + row batches; a prepared
    INSERT fanned out with execute_concurrent. Table dropped + recreated each run (idempotent)."""
    import tempfile
    import uuid

    from cassandra.concurrent import execute_concurrent_with_args

    ks = f"datasets_{cfg.domain}"
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        table = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk
            pf = pq.ParquetFile(tmp.name)
            if pf.metadata.num_rows == 0:
                out[f"{ks}.{table}"] = 0
                continue
            peek = next(pf.iter_batches(batch_size=256)).to_pandas()   # dtypes + column order
            cols = [_sql_ident(c) for c in peek.columns]
            cql_types, casters = map(list, zip(*[_cql_col(peek[c].dtype) for c in peek.columns]))

            partition = _sql_ident(partition_raw) if partition_raw else None
            if partition and partition not in cols:
                log.warning(f"cassandra {ks}.{table}: partition col {partition!r} not present in "
                            f"{cols[:12]} — falling back to row_id-only key (plain dump)")
                partition = None
            if partition:
                # A partition key can't be null/empty ("Key may not be empty" — one blank fails the batch).
                # Force it to text + a sentinel for null/NaN/"" so every row lands and stays queryable.
                pi = cols.index(partition)
                cql_types[pi] = "text"
                casters[pi] = lambda v: "__UNKNOWN__" if (v is None or v != v or str(v) == "") else str(v)
            pk = f'PRIMARY KEY (("{_q(partition)}"), row_id)' if partition else "PRIMARY KEY (row_id)"

            col_defs = ", ".join(f'"{_q(c)}" {t}' for c, t in zip(cols, cql_types))
            session.execute(f"DROP TABLE IF EXISTS {_safe_ident(ks)}.{_safe_ident(table)}")  # nosemgrep
            session.execute(f'CREATE TABLE {_safe_ident(ks)}.{_safe_ident(table)} ({col_defs}, row_id uuid, {pk})')  # nosemgrep

            quoted = ", ".join(f'"{_q(c)}"' for c in cols)
            marks = ", ".join(["?"] * (len(cols) + 1))
            ins = session.prepare(f'INSERT INTO {ks}.{table} ({quoted}, row_id) VALUES ({marks})')

            n = 0
            for batch in pf.iter_batches(batch_size=_CQL_BATCH):
                df = batch.to_pandas()
                params = [
                    tuple(casters[i](v) for i, v in enumerate(rec)) + (uuid.uuid4(),)
                    for rec in df.itertuples(index=False, name=None)
                ]
                execute_concurrent_with_args(session, ins, params, concurrency=64)
                n += len(params)
                del batch, df, params
            out[f"{ks}.{table}"] = n
            log.info(f"cassandra {ks}.{table}: {n:,} rows"
                     + (f" (partition={partition})" if partition else " (row_id key)"))
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[f"{ks}.{table}"] = f"ERROR: {e}"
            log.error(f"cassandra {table}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


_OS_BATCH = 5_000


def _opensearch_client():
    from opensearchpy import OpenSearch

    host = os.environ.get("OPENSEARCH_HOST", "opensearch-cluster-master.opensearch.svc.cluster.local")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    # standalone playground has the security plugin OFF → plain HTTP, no auth.
    return OpenSearch(hosts=[{"host": host, "port": port}], use_ssl=False, verify_certs=False, http_compress=True)


def _load_dataset_to_opensearch(client, mc, cfg, dataset, log) -> dict:
    """Each silver parquet file → an OpenSearch index (doc per row) — searchable. MEMORY-SAFE: temp file + row
    batches → helpers.bulk. Index dropped + recreated each run (idempotent). Index name = sanitized file name
    (OpenSearch requires lowercase/no special chars — _sql_ident already does that)."""
    import tempfile

    from opensearchpy import helpers

    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        index = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            client.indices.delete(index=index, ignore=[404])
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk
            n = 0
            for batch in pq.ParquetFile(tmp.name).iter_batches(batch_size=_OS_BATCH):
                actions = ({"_index": index, "_source": doc} for doc in batch.to_pylist())
                ok, _errs = helpers.bulk(client, actions, chunk_size=_OS_BATCH, raise_on_error=False)
                n += ok
                del batch
            client.indices.refresh(index=index)
            out[index] = n
            log.info(f"opensearch {index}: {n:,} docs")
        except Exception as e:  # noqa: BLE001 — per-index resilience
            out[index] = f"ERROR: {e}"
            log.error(f"opensearch {index}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


def _clickhouse_client(database="default"):
    import clickhouse_connect

    host = os.environ.get("CLICKHOUSE_HOST", "clickhouse.data-mesh.svc.cluster.local")
    port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    user = os.environ.get("CLICKHOUSE_USER", "default")
    # ClickHouse now requires a password (set via the users.d Secret — DataHub's clickhouse-sqlalchemy can't
    # do no-auth). Password comes from CLICKHOUSE_PASSWORD (secretKeyRef in user-code.yaml → clickhouse-secret),
    # NOT a hardcoded default — empty fallback fails auth loudly rather than embedding the real secret in code.
    pw = os.environ.get("CLICKHOUSE_PASSWORD", "")
    return clickhouse_connect.get_client(host=host, port=port, username=user, password=pw, database=database)


def _load_dataset_to_clickhouse(client, mc, cfg, dataset, log) -> dict:
    """Each silver parquet file → a MergeTree table in db datasets_<domain>. NATIVE ingest: ClickHouse reads
    the parquet straight from the lakeFS S3 gateway via the s3() table function (schema inferred, columnar,
    memory-bounded server-side) — CREATE TABLE … ORDER BY tuple() AS SELECT * FROM s3(…). Fast even for
    musicbrainz/OFF (no Python row loop). Table dropped + recreated each run (idempotent). lakeFS creds are
    passed as bound params so the secret stays out of the query text/logs."""
    db = f"datasets_{cfg.domain}"
    ep = io.endpoint()
    host = ep.replace("https://", "").replace("http://", "")
    scheme = "https" if ep.startswith("https://") else "http"
    key = os.environ["LAKEFS_ACCESS_KEY_ID"]
    secret = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        table = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        s3url = f"{scheme}://{host}/{cfg.repo}/{obj.object_name}"   # lakeFS S3 gateway URL for s3()
        try:
            client.command(f"DROP TABLE IF EXISTS `{db}`.`{table}`")
            client.command(
                f"CREATE TABLE `{db}`.`{table}` ENGINE = MergeTree ORDER BY tuple() AS "
                "SELECT * FROM s3({url:String}, {k:String}, {s:String}, 'Parquet') "
                # skip all-null parquet columns (Parquet 'null' type → ClickHouse can't schema-infer it);
                # they carry no data, so dropping them is lossless (3 usda tables had one each).
                "SETTINGS input_format_parquet_skip_columns_with_unsupported_types_in_schema_inference = 1",
                parameters={"url": s3url, "k": key, "s": secret},
            )
            n = int(client.command(f"SELECT count() FROM `{db}`.`{table}`"))
            out[f"{db}.{table}"] = n
            log.info(f"clickhouse {db}.{table}: {n:,} rows (native s3 ingest)")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[f"{db}.{table}"] = f"ERROR: {e}"
            log.error(f"clickhouse {table}: {e}")
    return out


_NEO4J_BATCH = 25_000        # load: one managed tx per batch (node MERGEs + edge CREATEs commit atomically)
_NEO4J_CLEAR_BATCH = 1_000   # clear: DETACH DELETE drags each node's edges into the tx, so keep batches small
# Neo4j RANGE indexes (which uniqueness constraints build) reject keys over ~8KB. A key column can carry a
# corrupt/oversized value (lastfm had a 120KB "artist name") that would abort the whole batch tx, so MERGE
# filters skip any row whose key stringifies longer than this. Chars (not bytes) × ≤4 bytes/char stays under
# the limit; real ids/names/titles are tiny, so this only ever drops garbage.
_KEY_MAXLEN = 1000


def _neo4j_driver():
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_URI", "bolt://neo4j.weyland.svc.cluster.local:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ["NEO4J_PASSWORD"]   # secretKeyRef → neo4j-secret; no default (fail loud, no secret in code)
    # Resilience for the mesh: keep_alive + a short connection lifetime so stale Bolt connections are recycled,
    # and a generous transaction retry window so execute_write can re-establish a connection Envoy reset
    # (TCP-keepalive on the neo4j DestinationRule) mid-load instead of the load erroring out.
    return GraphDatabase.driver(uri, auth=(user, pw), keep_alive=True, max_connection_lifetime=120,
                                connection_acquisition_timeout=60, max_transaction_retry_time=180)


def _bt(name) -> str:
    """Backtick-quote a Cypher identifier (label / rel type / property / map key)."""
    return "`" + str(name).replace("`", "``") + "`"


def _neo4j_queries(spec):
    """Compile a GraphSpec into (constraint_cyphers, node_cyphers, edge_cyphers) — built ONCE, reused for every
    batch. node = {label, key, col?, props?}; edge = {rel, src:(label,key,col), dst:(label,key,col), props?}.
    Nodes are UNWIND+MERGE (index-backed, dedup-safe). Edges are UNWIND+MATCH-both-endpoints+CREATE: MERGE'ing
    a relationship into a supernode is O(degree) per row (it scans the node's existing rels to dedup) — death
    at scale (radiohead has ~40k listeners). CREATE is O(1); silver has one row per pair so no dup risk. MATCH
    (not MERGE) the endpoints means every edge endpoint label MUST also be a node spec (so the node load
    creates it first) — a self-ref root whose parent isn't present just matches nothing and stays a root."""
    constraints, seen = [], set()

    def _constrain(label, key):
        if (label, key) not in seen:
            seen.add((label, key))
            constraints.append(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{_bt(label)}) REQUIRE n.{_bt(key)} IS UNIQUE")

    node_q = []
    for nd in spec.get("nodes", []):
        label, key, col = nd["label"], nd["key"], nd.get("col", nd["key"])
        _constrain(label, key)
        q = (f"UNWIND $rows AS row WITH row "
             f"WHERE row.{_bt(col)} IS NOT NULL AND size(toString(row.{_bt(col)})) <= {_KEY_MAXLEN} "
             f"MERGE (n:{_bt(label)} {{{_bt(key)}: row.{_bt(col)}}})")
        if nd.get("props"):
            q += " SET " + ", ".join(f"n.{_bt(p)} = row.{_bt(p)}" for p in nd["props"])
        node_q.append(q)

    edge_q = []
    for ed in spec.get("edges", []):
        (sl, sk, sc), (dl, dk, dc) = ed["src"], ed["dst"]
        _constrain(sl, sk)
        _constrain(dl, dk)
        if ed.get("dst_list"):
            # dst column is a multi-value list, PARSED to a real list in Python first (_parse_list). UNWIND it
            # into one edge per element; dst is MERGE'd (not a single-value node spec); rel CREATE'd; src MATCH'd.
            # Two shapes: dst_list_key (track_genres → genre_id) keeps the real key type (int) so it MATCHes the
            # int-keyed :Genre nodes — DON'T toString it; a plain scalar list (audioset human_labels) is
            # toString'd + trimmed + size-guarded.
            if ed.get("dst_list_key"):
                q = (f"UNWIND $rows AS row WITH row "
                     f"WHERE row.{_bt(sc)} IS NOT NULL AND size(toString(row.{_bt(sc)})) <= {_KEY_MAXLEN} "
                     f"AND row.{_bt(dc)} IS NOT NULL "
                     f"MATCH (a:{_bt(sl)} {{{_bt(sk)}: row.{_bt(sc)}}}) "
                     f"UNWIND row.{_bt(dc)} AS _dv WITH a, _dv WHERE _dv IS NOT NULL "
                     f"MERGE (b:{_bt(dl)} {{{_bt(dk)}: _dv}}) "
                     f"CREATE (a)-[r:{_bt(ed['rel'])}]->(b)")
            else:
                q = (f"UNWIND $rows AS row WITH row "
                     f"WHERE row.{_bt(sc)} IS NOT NULL AND size(toString(row.{_bt(sc)})) <= {_KEY_MAXLEN} "
                     f"AND row.{_bt(dc)} IS NOT NULL "
                     f"MATCH (a:{_bt(sl)} {{{_bt(sk)}: row.{_bt(sc)}}}) "
                     f"UNWIND row.{_bt(dc)} AS _raw "
                     f"WITH a, trim(toString(_raw)) AS _dv WHERE _dv <> '' AND size(_dv) <= {_KEY_MAXLEN} "
                     f"MERGE (b:{_bt(dl)} {{{_bt(dk)}: _dv}}) "
                     f"CREATE (a)-[r:{_bt(ed['rel'])}]->(b)")
        else:
            q = (f"UNWIND $rows AS row WITH row "
                 f"WHERE row.{_bt(sc)} IS NOT NULL AND size(toString(row.{_bt(sc)})) <= {_KEY_MAXLEN} "
                 f"AND row.{_bt(dc)} IS NOT NULL AND size(toString(row.{_bt(dc)})) <= {_KEY_MAXLEN} "
                 f"MATCH (a:{_bt(sl)} {{{_bt(sk)}: row.{_bt(sc)}}}) "
                 f"MATCH (b:{_bt(dl)} {{{_bt(dk)}: row.{_bt(dc)}}}) "
                 f"CREATE (a)-[r:{_bt(ed['rel'])}]->(b)")
            if ed.get("props"):
                q += " SET " + ", ".join(f"r.{_bt(p)} = row.{_bt(p)}" for p in ed["props"])
        edge_q.append(q)

    return constraints, node_q, edge_q


def _parse_list(v, key=None):
    """Parse a multi-value cell into a list. Handles a real list/tuple, or a stringified Python-list literal
    (ast.literal_eval keeps commas that are INSIDE an element intact, e.g. "['Speech', 'Inside, small room']").
    key: when the elements are dicts (fma_tracks track_genres = "[{'genre_id': '21', ...}]"), extract this
    field from each; numeric-string ids are coerced to int so they MATCH int node keys (the :Genre genre_id)."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        items = list(v)
    else:
        s = str(v).strip()
        if not s:
            return []
        try:
            import ast
            parsed = ast.literal_eval(s)
            items = list(parsed) if isinstance(parsed, (list, tuple)) else [parsed]
        except (ValueError, SyntaxError):
            if key is not None:
                return []   # can't bracket-split into dicts
            return [p.strip(" '\"[]") for p in s.strip("[]").split(",") if p.strip(" '\"[]")]
    if key is not None:
        out = []
        for el in items:
            val = el.get(key) if isinstance(el, dict) else None
            if val is None:
                continue
            out.append(int(val) if isinstance(val, str) and val.lstrip("-").isdigit() else val)
        return out
    return [str(x) for x in items]


def _write_neo4j_batch(tx, node_q, edge_q, rows):
    """One batch = one managed transaction: node MERGEs + edge CREATEs commit together (atomic — so an
    execute_write RETRY after a dropped connection re-does the whole batch cleanly and never double-CREATEs
    edges). Passed to session.execute_write, which retries it on transient/connection errors."""
    for q in node_q:
        tx.run(q, rows=rows)
    for q in edge_q:
        tx.run(q, rows=rows)


def _load_dataset_to_neo4j(driver, mc, cfg, dataset, spec, log) -> dict:
    """Build a graph from silver Parquet per the GraphSpec — nodes + edges MERGE'd (idempotent; re-runs dedupe
    on the key, no drop needed). Uniqueness constraints are created FIRST (MERGE without the backing index is
    O(n) per row → catastrophic on lastfm's ~17M). MEMORY-SAFE: temp file + row batches (to_pylist → plain
    dicts of Python scalars the driver accepts) fed to batched UNWIND MERGE. One spec covers every parquet file
    under parquet/<dataset>/ (they share the schema). Columns are logged so a spec/column mismatch is visible
    (a wrong key column → WHERE ... IS NOT NULL filters every row out → 0 loaded, not a crash)."""
    import tempfile

    constraints, node_q, edge_q = _neo4j_queries(spec)
    labels = [nd["label"] for nd in spec.get("nodes", [])]
    list_cols = [(ed["dst"][2], ed.get("dst_list_key")) for ed in spec.get("edges", []) if ed.get("dst_list")]
    with driver.session() as s:
        for c in constraints:
            s.run(c)
        # clean rebuild — edges are CREATE'd (no dedup), so a re-run MUST start empty or it doubles
        # relationships. Batched DETACH DELETE (CALL {} IN TRANSACTIONS) keeps the wipe memory-bounded on big
        # graphs. Defaults to every node label, but a spec can override `clear_labels` to protect a label it
        # SHARES with another dataset (fma_tracks reuses lastfm's :Artist — clearing it would wipe the PLAYS
        # graph; it clears only Track/Album, and DETACH DELETE Track still removes this dataset's BY/ON edges).
        for label in spec.get("clear_labels", labels):
            log.info(f"neo4j {dataset}: clearing existing (:{label}) for clean rebuild")
            s.run(f"MATCH (n:{_bt(label)}) CALL {{ WITH n DETACH DELETE n }} "
                  f"IN TRANSACTIONS OF {_NEO4J_CLEAR_BATCH} ROWS")

    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        key = dataset if fname == dataset else f"{dataset}/{fname}"
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk
            pf = pq.ParquetFile(tmp.name)
            log.info(f"neo4j {dataset}: columns {list(pf.schema_arrow.names)[:24]}")
            n = 0
            milestone = 0
            with driver.session() as s:
                for batch in pf.iter_batches(batch_size=_NEO4J_BATCH):
                    rows = batch.to_pylist()
                    for lc, lkey in list_cols:                 # parse stringified-list cols to real lists
                        for r in rows:
                            r[lc] = _parse_list(r.get(lc), key=lkey)
                    # one auto-retried managed transaction per batch — recovers from a Bolt connection Envoy
                    # reset mid-load (no infinite hang), and atomicity means the retry can't double-CREATE.
                    s.execute_write(_write_neo4j_batch, node_q, edge_q, rows)
                    n += len(rows)
                    if n // 1_000_000 > milestone:   # progress heartbeat every ~1M rows
                        milestone = n // 1_000_000
                        log.info(f"neo4j {key}: {n:,} rows loaded so far")
                    del batch, rows
            out[key] = n
            log.info(f"neo4j {key}: {n:,} rows → {len(spec.get('nodes', []))} node type(s), "
                     f"{len(spec.get('edges', []))} edge type(s)")
        except Exception as e:  # noqa: BLE001 — per-dataset resilience
            out[key] = f"ERROR: {e}"
            log.error(f"neo4j {dataset}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


_VEC_UPSERT_BATCH = 1_000
_EMBEDDER = None


def _qdrant_client():
    from qdrant_client import QdrantClient

    host = os.environ.get("QDRANT_HOST", "qdrant.weyland.svc.cluster.local")
    port = int(os.environ.get("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port, timeout=300)   # 300s for the heavy one-time collection rewrites


def _weaviate_client():
    import weaviate

    host = os.environ.get("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local")
    return weaviate.connect_to_custom(
        http_host=host, http_port=int(os.environ.get("WEAVIATE_PORT", "8080")), http_secure=False,
        grpc_host=host, grpc_port=int(os.environ.get("WEAVIATE_GRPC_PORT", "50051")), grpc_secure=False)


def _embedder():
    """bge-small-en-v1.5 — the same model the RAG uses; loaded once per process."""
    global _EMBEDDER
    if _EMBEDDER is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDER = SentenceTransformer(os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5"))
    return _EMBEDDER


def _weaviate_class(domain, dataset):
    return "".join(p.capitalize() for p in f"datasets_{domain}_{dataset}".split("_"))


def _build_vectors(mc, cfg, dataset, spec, log):
    """Build (dim, records) for a dataset from silver Parquet — the SHARED step both vector backends consume.
    records = [{id, vector, payload}]. Numeric specs assemble feature columns z-score-normalized (raw features
    span wild scales → cosine similarity is meaningless without it); text specs concat the columns and embed
    with bge-small (already unit-normalized). Payload values are stringified (JSON/GraphQL-safe)."""
    import tempfile
    import numpy as np
    import pandas as pd

    prefix = f"{io.branch()}/parquet/{dataset}/"
    frames = []
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)
            frames.append(pd.read_parquet(tmp.name))
        finally:
            os.unlink(tmp.name)
    if not frames:
        return 0, []
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    if spec.get("text"):
        cols = [c for c in spec["text"] if c in df.columns]
        texts = df[cols].fillna("").astype(str).agg(" ".join, axis=1).tolist()
        vecs = _embedder().encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        vectors = [v.tolist() for v in vecs]
        dim = len(vectors[0]) if vectors else 384
        log.info(f"{dataset}: text vectors dim={dim} from {cols} ({len(df):,} rows)")
    else:
        if spec.get("numeric"):
            cols = [c for c in spec["numeric"] if c in df.columns]
        else:
            excl = set(spec.get("numeric_exclude", [])) | ({spec["id"]} if spec.get("id") else set())
            cols = [c for c in df.columns if c not in excl and pd.api.types.is_numeric_dtype(df[c])]
        mat = df[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
        mu, sd = mat.mean(axis=0), mat.std(axis=0)
        sd[sd == 0] = 1.0
        mat = np.nan_to_num((mat - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0)
        vectors = mat.tolist()
        dim = len(cols)
        log.info(f"{dataset}: numeric vectors dim={dim} (z-scored) from {cols[:6]}… ({len(df):,} rows)")

    id_col = spec.get("id")
    ids = df[id_col].astype(str).tolist() if id_col and id_col in df.columns else [str(i) for i in range(len(df))]
    pcols = [p for p in spec.get("payload", []) if p in df.columns]
    payloads = df[pcols].fillna("").astype(str).to_dict("records") if pcols else [{} for _ in range(len(df))]
    records = [{"id": ids[i], "vector": vectors[i], "payload": {"row_id": ids[i], **payloads[i]}}
               for i in range(len(df))]
    return dim, records


def _load_dataset_to_qdrant(client, dim, records, coll, log) -> int:
    """Recreate the collection (cosine) and upsert every record. Point id = sequential int (Qdrant ids must be
    int/UUID); the original id lives in the payload's row_id."""
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client.recreate_collection(coll, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    n = 0
    for s in range(0, len(records), _VEC_UPSERT_BATCH):
        chunk = records[s:s + _VEC_UPSERT_BATCH]
        pts = [PointStruct(id=s + j, vector=r["vector"], payload=r["payload"]) for j, r in enumerate(chunk)]
        client.upsert(collection_name=coll, points=pts)
        n += len(pts)
    log.info(f"qdrant {coll}: {n:,} points (dim {dim})")
    return n


def _load_dataset_to_weaviate(client, dim, records, cls, log) -> int:
    """Drop + recreate the class (BYO vectors, vectorizer none) and batch-insert. Payload keys → TEXT props."""
    from weaviate.classes.config import Configure, DataType, Property

    if cls in {c.name for c in client.collections.list_all().values()}:
        client.collections.delete(cls)
    keys = list(records[0]["payload"].keys()) if records else ["row_id"]
    client.collections.create(
        name=cls, vectorizer_config=Configure.Vectorizer.none(),
        properties=[Property(name=k, data_type=DataType.TEXT) for k in keys])
    col = client.collections.get(cls)
    n = 0
    with col.batch.dynamic() as batch:
        for r in records:
            batch.add_object(properties=r["payload"], vector=r["vector"])
            n += 1
    log.info(f"weaviate {cls}: {n:,} objects (dim {dim})")
    return n


def _lancedb_connect(cfg):
    """Open a LanceDB database on the lakeFS S3 gateway (proven creds/endpoint already on the pod). LanceDB is
    EMBEDDED — no server; it reads/writes Lance datasets straight from object storage and does ANN in-process.
    One db per domain at s3://<repo>/<branch>/lancedb/, a table per dataset."""
    import lancedb

    ep = io.endpoint()
    scheme = "https" if ep.startswith("https") else "http"
    host = ep.replace("https://", "").replace("http://", "")
    uri = f"s3://{cfg.repo}/{io.branch()}/lancedb"
    storage_options = {
        "aws_endpoint": f"{scheme}://{host}",
        "aws_access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
        "aws_secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        "aws_region": "us-east-1",
        "aws_allow_http": "true" if scheme == "http" else "false",
        "aws_virtual_hosted_style_request": "false",   # path-style — lakeFS/MinIO S3 gateway
    }
    return lancedb.connect(uri, storage_options=storage_options)


def _load_dataset_to_lancedb(db, dim, records, table, log) -> int:
    """Drop + recreate a LanceDB table from the shared _build_vectors output (row_id + vector + payload). Builds
    an ANN index when the table is large enough (small tables do exact search fine). Fixed-size vector column so
    the index is buildable."""
    import pyarrow as pa

    if table in db.table_names():
        db.drop_table(table)
    keys = list(records[0]["payload"].keys()) if records else ["row_id"]
    flat = pa.array([x for r in records for x in r["vector"]], type=pa.float32())
    arrays = {"vector": pa.FixedSizeListArray.from_arrays(flat, dim)}
    for k in keys:
        arrays[k] = pa.array([str(r["payload"].get(k, "")) for r in records], type=pa.string())
    tbl = db.create_table(table, pa.table(arrays))
    try:
        if len(records) >= 2_000:   # IVF index only pays off past a few thousand rows
            tbl.create_index(metric="cosine", vector_column_name="vector")
    except Exception as e:  # noqa: BLE001 — index is an optimization; exact search works without it
        log.warning(f"lancedb {table}: index skipped ({e})")
    log.info(f"lancedb {table}: {len(records):,} rows (dim {dim})")
    return len(records)


def build_store_load_assets(cfg):
    """Return the per-store loader assets this domain needs (only stores with a non-empty allowlist)."""
    assets = []
    d = cfg.domain

    if cfg.mysql_allow:
        @asset(
            name=f"datasets_{d}_mysql_load",
            group_name=f"datasets_{d}_stores",  # own group — NOT the transform group, so the transform job won't run it
            deps=[f"datasets_{d}_parquet"],  # reads silver after it exists; parquet's no_failures check gates it
            description=f"Hydrate MySQL from silver Parquet — db per dataset, table per file ({len(cfg.mysql_allow)} datasets).",
        )
        def _mysql_load(context):
            mc = io.client()
            engine_for = _mysql_engine_factory()
            out = {}
            for dataset in sorted(cfg.mysql_allow):
                out.update(_load_dataset_to_mysql(mc, cfg, dataset, engine_for, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_mysql_load)

    if cfg.timescale_allow:
        @asset(
            name=f"datasets_{d}_timescaledb_load",
            group_name=f"datasets_{d}_stores",   # same stores group → runs in the hydrate job, not the transform
            deps=[f"datasets_{d}_parquet"],       # gated by the parquet no_failures check
            description=f"Hydrate TimescaleDB hypertables from silver Parquet ({len(cfg.timescale_allow)} dataset(s)).",
        )
        def _timescale_load(context):
            mc = io.client()
            engine = _tsdb_engine()
            out = {}
            for dataset, time_col in sorted(cfg.timescale_allow.items()):
                out.update(_load_dataset_to_timescale(mc, cfg, dataset, time_col, engine, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "hypertables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_timescale_load)

    if cfg.mongo_allow:
        # datasets from the broker's parquet + any that come from a dedicated streamed asset (OFF)
        _mongo_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(cfg.mongo_allow & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_mongodb_load",
            group_name=f"datasets_{d}_stores",
            deps=_mongo_deps,
            description=f"Hydrate MongoDB collections from silver Parquet ({len(cfg.mongo_allow)} datasets).",
        )
        def _mongo_load(context):
            mc = io.client()
            client = _mongo_client()
            out = {}
            try:
                for dataset in sorted(cfg.mongo_allow):
                    out.update(_load_dataset_to_mongo(mc, cfg, dataset, client, context.log))
            finally:
                client.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "collections_loaded": MetadataValue.int(ok),
                "docs_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_mongo_load)

    if cfg.cockroach_allow:
        _cr_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(cfg.cockroach_allow & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_cockroachdb_load",
            group_name=f"datasets_{d}_stores",
            deps=_cr_deps,
            description=f"Hydrate CockroachDB (db per dataset, table per file) from silver Parquet ({len(cfg.cockroach_allow)} datasets).",
        )
        def _cockroach_load(context):
            mc = io.client()
            engine_for = _cockroach_engine_factory()
            out = {}
            for dataset in sorted(cfg.cockroach_allow):
                out.update(_load_dataset_to_cockroach(mc, cfg, dataset, engine_for, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_cockroach_load)

    if cfg.cassandra_allow:
        _ca_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(set(cfg.cassandra_allow) & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_cassandra_load",
            group_name=f"datasets_{d}_stores",
            deps=_ca_deps,
            description=f"Hydrate Cassandra (keyspace datasets_{d}, table per file) from silver Parquet ({len(cfg.cassandra_allow)} datasets).",
        )
        def _cassandra_load(context):
            mc = io.client()
            cluster = _cassandra_cluster()
            session = cluster.connect()
            session.default_timeout = 60
            session.execute(
                f"CREATE KEYSPACE IF NOT EXISTS datasets_{d} "
                "WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}")
            out = {}
            try:
                for dataset, partition_col in sorted(cfg.cassandra_allow.items()):
                    out.update(_load_dataset_to_cassandra(session, mc, cfg, dataset, partition_col, context.log))
            finally:
                cluster.shutdown()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_cassandra_load)

    if cfg.opensearch_allow:
        _os_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(cfg.opensearch_allow & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_opensearch_load",
            group_name=f"datasets_{d}_stores",
            deps=_os_deps,
            description=f"Bulk-index into OpenSearch (index per file, doc per row) from silver Parquet ({len(cfg.opensearch_allow)} datasets).",
        )
        def _opensearch_load(context):
            mc = io.client()
            client = _opensearch_client()
            out = {}
            for dataset in sorted(cfg.opensearch_allow):
                out.update(_load_dataset_to_opensearch(client, mc, cfg, dataset, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "indices_loaded": MetadataValue.int(ok),
                "docs_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_opensearch_load)

    if cfg.clickhouse_allow:
        _ch_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(cfg.clickhouse_allow & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_clickhouse_load",
            group_name=f"datasets_{d}_stores",
            deps=_ch_deps,
            description=f"Hydrate ClickHouse (db datasets_{d}, MergeTree per file, native s3 ingest) from silver Parquet ({len(cfg.clickhouse_allow)} datasets).",
        )
        def _clickhouse_load(context):
            mc = io.client()
            client = _clickhouse_client()
            out = {}
            try:
                client.command(f"CREATE DATABASE IF NOT EXISTS `datasets_{d}`")
                for dataset in sorted(cfg.clickhouse_allow):
                    out.update(_load_dataset_to_clickhouse(client, mc, cfg, dataset, context.log))
            finally:
                client.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_clickhouse_load)

    if cfg.neo4j_allow:
        _neo_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(set(cfg.neo4j_allow) & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_neo4j_load",
            group_name=f"datasets_{d}_stores",
            deps=_neo_deps,
            description=f"Build Neo4j graphs (nodes + edges per GraphSpec) from silver Parquet ({len(cfg.neo4j_allow)} datasets).",
        )
        def _neo4j_load(context):
            mc = io.client()
            driver = _neo4j_driver()
            out = {}
            try:
                for dataset, spec in sorted(cfg.neo4j_allow.items()):
                    out.update(_load_dataset_to_neo4j(driver, mc, cfg, dataset, spec, context.log))
            finally:
                driver.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "graphs_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_neo4j_load)

    if cfg.vector_allow:
        _vec_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(set(cfg.vector_allow) & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_qdrant_load",
            group_name=f"datasets_{d}_stores",
            deps=_vec_deps,
            description=f"Vectorize silver → Qdrant (collection per dataset, cosine) for {len(cfg.vector_allow)} datasets.",
        )
        def _qdrant_load(context):
            mc = io.client()
            client = _qdrant_client()
            out = {}
            try:
                for dataset, spec in sorted(cfg.vector_allow.items()):
                    try:
                        dim, records = _build_vectors(mc, cfg, dataset, spec, context.log)
                        coll = f"datasets_{d}_{dataset}"
                        out[coll] = _load_dataset_to_qdrant(client, dim, records, coll, context.log) if records else 0
                    except Exception as e:  # noqa: BLE001 — per-dataset resilience
                        out[dataset] = f"ERROR: {e}"
                        context.log.error(f"qdrant {dataset}: {e}")
            finally:
                client.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "collections_loaded": MetadataValue.int(ok),
                "vectors_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_qdrant_load)

        @asset(
            name=f"datasets_{d}_weaviate_load",
            group_name=f"datasets_{d}_stores",
            deps=_vec_deps,
            description=f"Vectorize silver → Weaviate (class per dataset, BYO vectors) for {len(cfg.vector_allow)} datasets.",
        )
        def _weaviate_load(context):
            mc = io.client()
            client = _weaviate_client()
            out = {}
            try:
                for dataset, spec in sorted(cfg.vector_allow.items()):
                    try:
                        dim, records = _build_vectors(mc, cfg, dataset, spec, context.log)
                        cls = _weaviate_class(d, dataset)
                        out[cls] = _load_dataset_to_weaviate(client, dim, records, cls, context.log) if records else 0
                    except Exception as e:  # noqa: BLE001 — per-dataset resilience
                        out[dataset] = f"ERROR: {e}"
                        context.log.error(f"weaviate {dataset}: {e}")
            finally:
                client.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "classes_loaded": MetadataValue.int(ok),
                "objects_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_weaviate_load)

    _lancedb_specs = cfg.lancedb_allow or cfg.vector_allow   # defaults to the same vectors as Qdrant/Weaviate
    if _lancedb_specs:
        _lc_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(set(_lancedb_specs) & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_lancedb_load",
            group_name=f"datasets_{d}_stores",
            deps=_lc_deps,
            description=f"Build LanceDB tables (embedded, Lance-native, on object storage) for {len(_lancedb_specs)} datasets.",
        )
        def _lancedb_load(context):
            mc = io.client()
            db = _lancedb_connect(cfg)
            out = {}
            for dataset, spec in sorted(_lancedb_specs.items()):
                try:
                    dim, records = _build_vectors(mc, cfg, dataset, spec, context.log)
                    out[dataset] = _load_dataset_to_lancedb(db, dim, records, dataset, context.log) if records else 0
                except Exception as e:  # noqa: BLE001 — per-dataset resilience
                    out[dataset] = f"ERROR: {e}"
                    context.log.error(f"lancedb {dataset}: {e}")
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_lancedb_load)

    return assets
