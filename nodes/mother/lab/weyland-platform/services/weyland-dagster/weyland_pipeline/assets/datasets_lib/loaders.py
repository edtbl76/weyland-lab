"""Store hydration (data-store-mageddon): the third datasets_lib factory. build_store_load_assets(cfg) reads silver
Parquet from lakeFS and loads it into the Tier-2 stores the grid targets, one loader asset per store, driven by the
explicit per-store allowlists on DomainConfig (a store gets an asset only when its allowlist is non-empty).

The stores are a table (`_STORES`): adding a store is a row plus its loader module, not another branch here. The
loaders live in the store_* modules; the names other modules and the tests import from here are re-exported below.
"""
from dataclasses import dataclass
from typing import Callable

from dagster import MetadataValue, Output, asset

from . import io
from .store_cassandra import _cassandra_cluster, _cassandra_write_file, _cql_col, _load_dataset_to_cassandra
from .store_common import _q, _safe_ident, _sql_ident
from .store_docs import (_clickhouse_client, _load_dataset_to_clickhouse, _load_dataset_to_mongo,
                         _load_dataset_to_opensearch, _mongo_client, _opensearch_client)
from .store_neo4j import _bt, _load_dataset_to_neo4j, _neo4j_driver, _neo4j_queries, _parse_list
from .store_sql import (_cockroach_engine_factory, _load_dataset_to_cockroach, _load_dataset_to_mysql,
                        _load_dataset_to_timescale, _mysql_engine_factory, _tsdb_engine)
from .store_vectors import (_build_vectors, _lancedb_connect, _load_dataset_to_lancedb, _load_dataset_to_qdrant,
                            _load_dataset_to_weaviate, _qdrant_client, _weaviate_class, _weaviate_client)

__all__ = [
    "build_store_load_assets", "io",
    "_bt", "_build_vectors", "_cassandra_write_file", "_cql_col", "_lancedb_connect", "_load_dataset_to_cassandra",
    "_load_dataset_to_clickhouse", "_load_dataset_to_cockroach", "_load_dataset_to_lancedb", "_load_dataset_to_mongo",
    "_load_dataset_to_mysql", "_load_dataset_to_neo4j", "_load_dataset_to_opensearch", "_load_dataset_to_qdrant",
    "_load_dataset_to_timescale", "_load_dataset_to_weaviate", "_mongo_client", "_neo4j_queries", "_parse_list",
    "_q", "_qdrant_client", "_safe_ident", "_sql_ident", "_weaviate_class", "_weaviate_client",
]


def _each(items, load):
    """Merge each item's per-table results into one dict."""
    out = {}
    for item in items:
        out.update(load(item))
    return out


def _closing(resource, close, work):
    """Run work(resource) and always release the resource."""
    try:
        return work(resource)
    finally:
        close(resource)


def _run_mysql(mc, cfg, allow, log):
    engine_for = _mysql_engine_factory()
    return _each(sorted(allow), lambda ds: _load_dataset_to_mysql(mc, cfg, ds, engine_for, log))


def _run_timescale(mc, cfg, allow, log):
    engine = _tsdb_engine()
    return _each(sorted(allow.items()), lambda it: _load_dataset_to_timescale(mc, cfg, it[0], it[1], engine, log))


def _run_mongo(mc, cfg, allow, log):
    return _closing(_mongo_client(), lambda c: c.close(), lambda client: _each(
        sorted(allow), lambda ds: _load_dataset_to_mongo(mc, cfg, ds, client, log)))


def _run_cockroach(mc, cfg, allow, log):
    engine_for = _cockroach_engine_factory()
    return _each(sorted(allow), lambda ds: _load_dataset_to_cockroach(mc, cfg, ds, engine_for, log))


def _run_cassandra(mc, cfg, allow, log):
    cluster = _cassandra_cluster()
    session = cluster.connect()
    # 2026-08-07: single-node Cassandra batch writes blow past 60s under hydrate I/O contention ("Client request
    # timeout", big_five). 300s tolerates the slow-but-progressing write.
    session.default_timeout = 300
    session.execute(f"CREATE KEYSPACE IF NOT EXISTS datasets_{cfg.domain} "
                    "WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}")
    return _closing(cluster, lambda c: c.shutdown(), lambda _c: _each(
        sorted(allow.items()), lambda it: _load_dataset_to_cassandra(session, mc, cfg, it[0], it[1], log)))


def _run_opensearch(mc, cfg, allow, log):
    client = _opensearch_client()
    return _each(sorted(allow), lambda ds: _load_dataset_to_opensearch(client, mc, cfg, ds, log))


def _run_clickhouse(mc, cfg, allow, log):
    def work(client):
        client.command(f"CREATE DATABASE IF NOT EXISTS `datasets_{cfg.domain}`")
        return _each(sorted(allow), lambda ds: _load_dataset_to_clickhouse(client, mc, cfg, ds, log))

    return _closing(_clickhouse_client(), lambda c: c.close(), work)


def _run_neo4j(mc, cfg, allow, log):
    return _closing(_neo4j_driver(), lambda d: d.close(), lambda driver: _each(
        sorted(allow.items()), lambda it: _load_dataset_to_neo4j(driver, mc, cfg, it[0], it[1], log)))


def _vector_loads(mc, cfg, specs, log, store, target, load):
    """Build each dataset's vectors and load them; a dataset's failure is recorded under its name, never raised."""
    out = {}
    for dataset, spec in sorted(specs.items()):
        try:
            dim, records = _build_vectors(mc, cfg, dataset, spec, log)
            name = target(dataset)
            out[name] = load(dim, records, name) if records else 0
        except Exception as e:  # noqa: BLE001 - per-dataset resilience
            out[dataset] = f"ERROR: {e}"
            log.error(f"{store} {dataset}: {e}")
    return out


def _run_qdrant(mc, cfg, specs, log):
    return _closing(_qdrant_client(), lambda c: c.close(), lambda client: _vector_loads(
        mc, cfg, specs, log, "qdrant", lambda ds: f"datasets_{cfg.domain}_{ds}",
        lambda dim, records, coll: _load_dataset_to_qdrant(client, dim, records, coll, log)))


def _run_weaviate(mc, cfg, specs, log):
    return _closing(_weaviate_client(), lambda c: c.close(), lambda client: _vector_loads(
        mc, cfg, specs, log, "weaviate", lambda ds: _weaviate_class(cfg.domain, ds),
        lambda dim, records, cls: _load_dataset_to_weaviate(client, dim, records, cls, log)))


def _run_lancedb(mc, cfg, specs, log):
    db = _lancedb_connect(cfg)
    return _vector_loads(mc, cfg, specs, log, "lancedb", lambda ds: ds,
                         lambda dim, records, table: _load_dataset_to_lancedb(db, dim, records, table, log))


@dataclass(frozen=True)
class _Store:
    asset: str                  # datasets_<domain>_<asset>_load
    allow: Callable             # cfg -> the allowlist (a set, or a dict of per-dataset specs)
    description: str            # formatted with {d} (domain) and {n} (allowlist size)
    run: Callable               # (mc, cfg, allow, log) -> {table: rows | "ERROR: ..."}
    loaded: str                 # metadata key for the count of tables that loaded
    total: str                  # metadata key for the summed rows
    streamed_deps: bool = True  # also depend on the per-dataset streamed parquet assets (OFF)


_STORES = [
    _Store("mysql", lambda c: c.mysql_allow,
           "Hydrate MySQL from silver Parquet — db per dataset, table per file ({n} datasets).",
           _run_mysql, "tables_loaded", "rows_total", streamed_deps=False),
    _Store("timescaledb", lambda c: c.timescale_allow,
           "Hydrate TimescaleDB hypertables from silver Parquet ({n} dataset(s)).",
           _run_timescale, "hypertables_loaded", "rows_total", streamed_deps=False),
    _Store("mongodb", lambda c: c.mongo_allow,
           "Hydrate MongoDB collections from silver Parquet ({n} datasets).",
           _run_mongo, "collections_loaded", "docs_total"),
    _Store("cockroachdb", lambda c: c.cockroach_allow,
           "Hydrate CockroachDB (db per dataset, table per file) from silver Parquet ({n} datasets).",
           _run_cockroach, "tables_loaded", "rows_total"),
    _Store("cassandra", lambda c: c.cassandra_allow,
           "Hydrate Cassandra (keyspace datasets_{d}, table per file) from silver Parquet ({n} datasets).",
           _run_cassandra, "tables_loaded", "rows_total"),
    _Store("opensearch", lambda c: c.opensearch_allow,
           "Bulk-index into OpenSearch (index per file, doc per row) from silver Parquet ({n} datasets).",
           _run_opensearch, "indices_loaded", "docs_total"),
    _Store("clickhouse", lambda c: c.clickhouse_allow,
           "Hydrate ClickHouse (db datasets_{d}, MergeTree per file, native s3 ingest) from silver Parquet "
           "({n} datasets).",
           _run_clickhouse, "tables_loaded", "rows_total"),
    _Store("neo4j", lambda c: c.neo4j_allow,
           "Build Neo4j graphs (nodes + edges per GraphSpec) from silver Parquet ({n} datasets).",
           _run_neo4j, "graphs_loaded", "rows_total"),
    _Store("qdrant", lambda c: c.vector_allow,
           "Vectorize silver → Qdrant (collection per dataset, cosine) for {n} datasets.",
           _run_qdrant, "collections_loaded", "vectors_total"),
    _Store("weaviate", lambda c: c.vector_allow,
           "Vectorize silver → Weaviate (class per dataset, BYO vectors) for {n} datasets.",
           _run_weaviate, "classes_loaded", "objects_total"),
    _Store("lancedb", lambda c: c.lancedb_allow or c.vector_allow,   # defaults to the Qdrant/Weaviate vectors
           "Build LanceDB tables (embedded, Lance-native, on object storage) for {n} datasets.",
           _run_lancedb, "tables_loaded", "rows_total"),
]


def _summary(out, loaded, total):
    counts = [v for v in out.values() if isinstance(v, int)]
    return Output(out, metadata={loaded: MetadataValue.int(len(counts)),
                                 total: MetadataValue.int(sum(counts)),
                                 "detail": MetadataValue.json(out)})


def _store_asset(cfg, store, allow):
    """One loader asset. It sits in the domain's own stores group (NOT the transform group, so the transform job
    never runs it) and depends on the silver parquet asset, whose no_failures check gates it."""
    d = cfg.domain
    deps = [f"datasets_{d}_parquet"]
    if store.streamed_deps:
        deps += [f"datasets_{d}_{ds}_parquet" for ds in sorted(set(allow) & cfg.streamed_parquet)]

    @asset(name=f"datasets_{d}_{store.asset}_load", group_name=f"datasets_{d}_stores", deps=deps,
           description=store.description.format(d=d, n=len(allow)))
    def _load(context):
        return _summary(store.run(io.client(), cfg, allow, context.log), store.loaded, store.total)

    return _load


def build_store_load_assets(cfg):
    """Return the per-store loader assets this domain needs (only stores with a non-empty allowlist)."""
    return [_store_asset(cfg, store, store.allow(cfg)) for store in _STORES if store.allow(cfg)]
