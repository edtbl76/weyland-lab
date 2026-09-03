"""Finance dataset fan-out transform — the explicit finance DomainConfig over the shared broker.

Same mechanism as music/health (datasets_lib): the only finance specifics are the repo, namespace, and the
allowlists. The finance raw layer is already tidy parquet (the FRED land asset shapes it, since the source
JSON is not a rectangle), which the broker's reader reads straight through. build_transform_assets()
produces datasets_finance_parquet/_arrow/_avro/_lance/_iceberg + _commit.

Phase 1 (B113) lands the FRED macro-series slice only: two tables (fred_macro, fred_series_meta), the base
silver formats, Iceberg gold, and two Tier-2 stores (TimescaleDB hypertable on fred_macro.date, ClickHouse
for both). Later phases add the remaining stores + sources — their allowlists stay empty here for now.
"""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks, build_vector_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.fred_parse import (
    CLICKHOUSE_ALLOW,
    ICEBERG_ALLOW,
    RAW_TABLES,
    TIMESCALE_ALLOW,
)
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.streaming_producer import build_stream_produce_assets

FINANCE_CFG = DomainConfig(
    domain="finance",
    repo="finance",
    namespace="datasets_finance",
    group_name="datasets_finance",
    land_deps=("datasets_finance_fred_land",),
    # Base silver formats — both raw tables. (Store loaders + the dbt mart read parquet/iceberg.)
    parquet_allow=RAW_TABLES, arrow_allow=RAW_TABLES, avro_allow=RAW_TABLES, iceberg_allow=ICEBERG_ALLOW,
    # TimescaleDB (Phase 1): one hypertable — fred_macro — time axis on the real observation `date`
    # (a full ISO date, NOT a year; the dtype-aware coercion in timeseries.hypertable_ts handles both).
    timescale_allow=TIMESCALE_ALLOW,
    # ClickHouse (Phase 1): both tables — native s3() ingest of the silver parquet.
    clickhouse_allow=CLICKHOUSE_ALLOW,
    # All other store allowlists (mysql/mongo/cockroach/cassandra/neo4j/opensearch/vector/lance/stream)
    # stay empty for Phase 1 — later phases add them.
)

(
    datasets_finance_parquet, datasets_finance_arrow, datasets_finance_avro,
    datasets_finance_lance, datasets_finance_iceberg, datasets_finance_commit,
) = build_transform_assets(FINANCE_CFG)

datasets_finance_checks = build_asset_checks(FINANCE_CFG) + build_vector_checks(FINANCE_CFG)
datasets_finance_store_assets = build_store_load_assets(FINANCE_CFG)
datasets_finance_stream_assets = build_stream_produce_assets(FINANCE_CFG)
