"""DomainConfig — the explicit, per-domain knobs the shared broker needs. Allowlists are written out as
literal sets (NOT derived from the storage grid): the grid is a guideline with free-text cells, and we
want the code to be the grep-able source of truth for what actually runs. Keyed by raw/ folder name."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainConfig:
    domain: str                          # "music" / "health" — drives asset names datasets_<domain>_<fmt>
    repo: str                            # lakeFS repo / bucket
    namespace: str                       # iceberg namespace, e.g. "datasets_music"
    group_name: str                      # dagster asset group
    land_deps: tuple = ()                # land asset names this transform depends on (asset-graph ordering)
    # per-format allowlists (raw/ folder names). A table absent from a format's set is skipped for that
    # format BEFORE the read. parquet/arrow/avro/iceberg are usually "all"; lance is selective.
    parquet_allow: frozenset = field(default_factory=frozenset)
    arrow_allow: frozenset = field(default_factory=frozenset)
    avro_allow: frozenset = field(default_factory=frozenset)
    lance_allow: frozenset = field(default_factory=frozenset)
    iceberg_allow: frozenset = field(default_factory=frozenset)

    # --- store hydration allowlists (data-store-mageddon) — which datasets target which Tier-2 store.
    # Explicit per the grid's store columns (a store gets a loader asset only when its allowlist is
    # non-empty). One field added per store as it's built.
    mysql_allow: frozenset = field(default_factory=frozenset)
    # TimescaleDB: {dataset: time_column} — the source column a hypertable's time axis is derived from
    # (e.g. WHO GHO {"who_gho": "TimeDim"} — TimeDim is the year). One hypertable per parquet file.
    timescale_allow: dict = field(default_factory=dict)
    # MongoDB: datasets to load as document collections (doc per parquet row), db datasets_<domain>.
    mongo_allow: frozenset = field(default_factory=frozenset)
    # CockroachDB: datasets to load as tables (pg-wire, db per dataset). Distributed SQL.
    cockroach_allow: frozenset = field(default_factory=frozenset)
    # Neo4j: {dataset: GraphSpec} — SELECTIVE + MODELED (grid Neo4j=Y = the 5 relationship-shaped music sets;
    # flat datasets are skipped, they live in the tabular/OLAP stores). A GraphSpec declares nodes + edges from
    # parquet columns; the loader creates unique constraints (MERGE without an index is catastrophic) then
    # batch-UNWIND-MERGEs. node = {label, key, col?, props}; edge = {rel, src:(label,key,col), dst:(...), props}.
    neo4j_allow: dict = field(default_factory=dict)
    # OpenSearch: datasets to bulk-index (index per parquet file, doc per row) into the standalone cluster
    # (ns opensearch, security OFF → no auth). Searchable; vector/kNN similarity is a later enhancement.
    opensearch_allow: frozenset = field(default_factory=frozenset)
    # ClickHouse: datasets to load as MergeTree tables (table per parquet file, db datasets_<domain>).
    # Columnar OLAP — ingested NATIVELY: ClickHouse reads the parquet from the lakeFS S3 gateway via the
    # s3() table function (schema inferred, no Python row loop). frozenset (no per-dataset knobs needed).
    clickhouse_allow: frozenset = field(default_factory=frozenset)
    # Cassandra: {dataset: partition_column_or_None}. Wide-column store — table per parquet file in
    # keyspace datasets_<domain>. The partition column (a natural key, e.g. who_gho → SpatialDim) makes it
    # query-first; a synthetic `row_id uuid` clustering col always guarantees row uniqueness. If the named
    # column isn't in the silver parquet, the loader falls back to a row_id-only key (plain dump) + logs.
    cassandra_allow: dict = field(default_factory=dict)
    # Qdrant + Weaviate (both grid=Y for the SAME sets): {dataset: vector_spec}. The vector is built ONCE per
    # dataset and upserted to BOTH backends (Qdrant collection + Weaviate class per dataset — dims differ, so
    # separate spaces). vector_spec is one of:
    #   {"numeric_exclude": [cols]}  → assemble ALL numeric cols except these into the vector, z-score normalized
    #   {"numeric": [cols]}          → assemble exactly these numeric cols, z-score normalized
    #   {"text": [cols]}             → concat these text cols per row + embed with bge-small (384-dim, unit-norm)
    # plus optional {"id": col} (point ref, else row index) and {"payload": [cols]} (stored for filter/display).
    vector_allow: dict = field(default_factory=dict)
    # LanceDB (grid LanceDB): same vector_spec shape — the embedded/Lance-native/object-storage-backed vector
    # store (no server, unlike Qdrant/Weaviate). Defaults to reusing vector_allow (same feature vectors, third
    # backend); set explicitly only to target a DIFFERENT set (e.g. add the larger-than-memory OFF that the
    # server DBs can't hold — LanceDB reads from object storage so it can).
    lancedb_allow: dict = field(default_factory=dict)
    # Redpanda (B1.5 streaming): {dataset: stream_spec} — the STREAM-shaped sets only (event/survey data, not
    # static bulk). Replays silver Parquet as Avro events into topic `datasets.<domain>.<dataset>`, schema
    # registered in the built-in Schema Registry (Confluent wire format). stream_spec: {"key": col_or_None,
    # "cap": int_or_None} — key = message key (partition/compaction), cap = max rows to replay (bound the huge
    # ones; a demo/"Avro in motion", not a bulk dump — genuinely event-driven change data comes via Debezium CDC).
    stream_allow: dict = field(default_factory=dict)
    # Datasets whose silver parquet comes from a dedicated STREAMED asset (datasets_<domain>_<ds>_parquet)
    # instead of the broker's datasets_<domain>_parquet — so store loaders can add it to their deps.
    streamed_parquet: frozenset = field(default_factory=frozenset)

    @property
    def producer(self) -> str:
        return f"datasets_{self.domain}"
