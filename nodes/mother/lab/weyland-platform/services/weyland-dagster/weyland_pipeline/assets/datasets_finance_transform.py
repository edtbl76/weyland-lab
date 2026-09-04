"""Finance dataset fan-out transform — the explicit finance DomainConfig over the shared broker.

Same mechanism as music/health (datasets_lib): the only finance specifics are the repo, namespace, and the
allowlists. The finance raw layer is already tidy parquet (the FRED land asset shapes it, since the source
JSON is not a rectangle), which the broker's reader reads straight through. build_transform_assets()
produces datasets_finance_parquet/_arrow/_avro/_lance/_iceberg + _commit.

Phase 1 (B113) lands the FRED macro-series slice: two tables (fred_macro, fred_series_meta), the base silver
formats, Iceberg gold, and two Tier-2 stores (TimescaleDB hypertable on fred_macro.date, ClickHouse for both).

Phase 2 (B113) adds the SEC EDGAR XBRL slice: two more tables (company_financials, company_meta) landed by
datasets_finance_edgar_land. They join the base silver formats + Iceberg gold + ClickHouse (annual financials
are NOT time-series, so they are deliberately absent from timescale_allow). The allowlists below UNION the FRED
and EDGAR constants so both slices flow through the one broker. mysql/mongo/cockroach/etc. stay empty for now —
a later phase expands EDGAR into them.
"""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks, build_vector_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.edgar_parse import (
    EDGAR_CLICKHOUSE_ALLOW,
    EDGAR_ICEBERG_ALLOW,
    EDGAR_RAW_TABLES,
)
from .datasets_lib.fred_parse import (
    CLICKHOUSE_ALLOW,
    ICEBERG_ALLOW,
    RAW_TABLES,
    TIMESCALE_ALLOW,
)
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.streaming_producer import build_stream_produce_assets

# Union the FRED (Phase 1) + EDGAR (Phase 2) table sets so both slices fan out through the shared broker.
_ALL_RAW_TABLES = RAW_TABLES | EDGAR_RAW_TABLES
_ALL_ICEBERG_ALLOW = ICEBERG_ALLOW | EDGAR_ICEBERG_ALLOW
_ALL_CLICKHOUSE_ALLOW = CLICKHOUSE_ALLOW | EDGAR_CLICKHOUSE_ALLOW

FINANCE_CFG = DomainConfig(
    domain="finance",
    repo="finance",
    namespace="datasets_finance",
    group_name="datasets_finance",
    land_deps=("datasets_finance_fred_land", "datasets_finance_edgar_land"),
    # Base silver formats — all four raw tables. (Store loaders + the dbt marts read parquet/iceberg.)
    parquet_allow=_ALL_RAW_TABLES, arrow_allow=_ALL_RAW_TABLES, avro_allow=_ALL_RAW_TABLES,
    iceberg_allow=_ALL_ICEBERG_ALLOW,
    # TimescaleDB: one hypertable — fred_macro — time axis on the real observation `date` (a full ISO date,
    # NOT a year; the dtype-aware coercion in timeseries.hypertable_ts handles both). EDGAR's annual financials
    # are NOT a hypertable, so timescale_allow stays FRED-only.
    timescale_allow=TIMESCALE_ALLOW,
    # ClickHouse: the analytical tables (fred_macro/meta + company_financials/meta) — native s3() ingest.
    clickhouse_allow=_ALL_CLICKHOUSE_ALLOW,
    # Neo4j (Phase 2 graph): the EDGAR company graph — (:Company)-[:IN_INDUSTRY]->(:SIC) from company_meta and
    # (:Company)-[:FILED]->(:Filing) from company_filings. Company is keyed by cik so both specs MERGE onto the
    # SAME nodes (the filing spec attaches to the companies the meta spec created). FRED is tabular, not graph.
    neo4j_allow={
        "company_meta": {
            "nodes": [
                {"label": "Company", "key": "cik", "props": ["ticker", "company", "exchange"]},
                {"label": "SIC", "key": "sic", "props": ["sic_description"]},
            ],
            "edges": [{"rel": "IN_INDUSTRY",
                       "src": ("Company", "cik", "cik"),
                       "dst": ("SIC", "sic", "sic"),
                       "props": []}],
        },
        "company_filings": {
            "nodes": [
                {"label": "Company", "key": "cik", "props": ["ticker"]},
                {"label": "Filing", "key": "accn", "props": ["form", "filed", "report_date"]},
            ],
            "edges": [{"rel": "FILED",
                       "src": ("Company", "cik", "cik"),
                       "dst": ("Filing", "accn", "accn"),
                       "props": []}],
        },
    },
    # mysql/mongo/cockroach/cassandra/opensearch/vector/lance/stream stay empty — a later phase expands EDGAR.
)

(
    datasets_finance_parquet, datasets_finance_arrow, datasets_finance_avro,
    datasets_finance_lance, datasets_finance_iceberg, datasets_finance_commit,
) = build_transform_assets(FINANCE_CFG)

datasets_finance_checks = build_asset_checks(FINANCE_CFG) + build_vector_checks(FINANCE_CFG)
datasets_finance_store_assets = build_store_load_assets(FINANCE_CFG)
datasets_finance_stream_assets = build_stream_produce_assets(FINANCE_CFG)
