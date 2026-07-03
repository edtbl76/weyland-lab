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
    # ClickHouse: datasets to load as MergeTree tables (table per parquet file, db datasets_<domain>).
    # Columnar OLAP — ingested NATIVELY: ClickHouse reads the parquet from the lakeFS S3 gateway via the
    # s3() table function (schema inferred, no Python row loop). frozenset (no per-dataset knobs needed).
    clickhouse_allow: frozenset = field(default_factory=frozenset)
    # Cassandra: {dataset: partition_column_or_None}. Wide-column store — table per parquet file in
    # keyspace datasets_<domain>. The partition column (a natural key, e.g. who_gho → SpatialDim) makes it
    # query-first; a synthetic `row_id uuid` clustering col always guarantees row uniqueness. If the named
    # column isn't in the silver parquet, the loader falls back to a row_id-only key (plain dump) + logs.
    cassandra_allow: dict = field(default_factory=dict)
    # Datasets whose silver parquet comes from a dedicated STREAMED asset (datasets_<domain>_<ds>_parquet)
    # instead of the broker's datasets_<domain>_parquet — so store loaders can add it to their deps.
    streamed_parquet: frozenset = field(default_factory=frozenset)

    @property
    def producer(self) -> str:
        return f"datasets_{self.domain}"
