"""Finance dataset fan-out transform — the explicit finance DomainConfig over the shared broker.

Same mechanism as music/health (datasets_lib): the only finance specifics are the repo, namespace, and the
allowlists. The finance raw layer is already tidy parquet (the FRED land asset shapes it, since the source
JSON is not a rectangle), which the broker's reader reads straight through. build_transform_assets()
produces datasets_finance_parquet/_arrow/_avro/_lance/_iceberg + _commit.

Phase 1 (B113) lands the FRED macro-series slice: two tables (fred_macro, fred_series_meta), the base silver
formats, Iceberg gold, and two Tier-2 stores (TimescaleDB hypertable on fred_macro.date, ClickHouse for both).

Phase 2 (B113) adds the SEC EDGAR XBRL slice: company_financials + company_meta (+ company_filings for the
graph) landed by datasets_finance_edgar_land. They join the base silver formats + Iceberg gold + ClickHouse +
CockroachDB + MySQL + MongoDB (annual financials are NOT time-series, so they are absent from timescale_allow).

Phase 3 (B113) adds the SEC EDGAR filings-TEXT slice: one table (filings_text) landed by
datasets_finance_edgar_text_land — section-aware 10-K narrative chunks that fan out to the VECTOR stores
(Qdrant/Weaviate/LanceDB) for the filings-RAG notebook, plus the base silver formats + Iceberg gold for a
Trino-queryable corpus.

Phase 4 (B113) adds the market OHLCV slice: one table (price_daily) landed by datasets_finance_market_land
(yfinance) — full daily-bar history for the same ~50 mega-caps → a Timescale hypertable on `date` + ClickHouse +
Cassandra (partitioned by ticker) + Iceberg gold + the mart_price_daily mart. The allowlists below UNION the
FRED + EDGAR-XBRL + filings-text + market constants so every slice flows through the one broker.
"""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks, build_vector_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.edgar_parse import (
    EDGAR_CLICKHOUSE_ALLOW,
    EDGAR_ICEBERG_ALLOW,
    EDGAR_RAW_TABLES,
)
from .datasets_lib.edgar_text_parse import FILINGS_TEXT_TABLES
from .datasets_lib.fred_parse import (
    CLICKHOUSE_ALLOW,
    ICEBERG_ALLOW,
    RAW_TABLES,
    TIMESCALE_ALLOW,
)
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.market_parse import PRICE_TABLES
from .datasets_lib.streaming_producer import build_stream_produce_assets

# Union the FRED (Phase 1) + EDGAR XBRL (Phase 2) + EDGAR filings-text (Phase 3) + market OHLCV (Phase 4) table
# sets so every slice fans out through the shared broker.
_ALL_RAW_TABLES = RAW_TABLES | EDGAR_RAW_TABLES | FILINGS_TEXT_TABLES | PRICE_TABLES
_ALL_ICEBERG_ALLOW = ICEBERG_ALLOW | EDGAR_ICEBERG_ALLOW | FILINGS_TEXT_TABLES | PRICE_TABLES
# ClickHouse: the analytical tables — FRED + EDGAR financials + the daily prices (native s3() ingest).
_ALL_CLICKHOUSE_ALLOW = CLICKHOUSE_ALLOW | EDGAR_CLICKHOUSE_ALLOW | PRICE_TABLES

FINANCE_CFG = DomainConfig(
    domain="finance",
    repo="finance",
    namespace="datasets_finance",
    group_name="datasets_finance",
    land_deps=("datasets_finance_fred_land", "datasets_finance_edgar_land",
               "datasets_finance_edgar_text_land", "datasets_finance_market_land"),
    # Base silver formats — all four raw tables. (Store loaders + the dbt marts read parquet/iceberg.)
    parquet_allow=_ALL_RAW_TABLES, arrow_allow=_ALL_RAW_TABLES, avro_allow=_ALL_RAW_TABLES,
    iceberg_allow=_ALL_ICEBERG_ALLOW,
    # TimescaleDB hypertables on a real `date` axis: fred_macro (Phase 1) + price_daily (Phase 4 — daily OHLCV
    # is the archetypal time-series). EDGAR's annual financials are NOT a hypertable, so they stay out. The
    # dtype-aware coercion in timeseries.hypertable_ts handles the full-date axis both tables carry.
    timescale_allow={**TIMESCALE_ALLOW, "price_daily": "date"},
    # ClickHouse: the analytical tables (fred_macro/meta + company_financials/meta) — native s3() ingest.
    clickhouse_allow=_ALL_CLICKHOUSE_ALLOW,
    # EDGAR store fan-out (Phase 2, "richest domain"): the structured financials + dim into every tabular/document
    # store (same tidy silver parquet the OLAP path reads; company_filings is graph-only). MySQL + MongoDB were
    # once excluded because the shared loaders choked on EDGAR's real data — both are now FIXED (general loader
    # defects, not finance-specific): the MySQL loader self-provisions its database (CREATE DATABASE IF NOT
    # EXISTS + the `--init-file` schema grant in mysql.yaml, so no per-dataset root grant), and the MongoDB
    # loader casts date columns to timestamp so BSON can encode them (`_mongo_encodable`).
    mysql_allow=frozenset({"company_financials", "company_meta"}),
    mongo_allow=frozenset({"company_financials", "company_meta"}),
    cockroach_allow=frozenset({"company_financials", "company_meta"}),
    # Cassandra (Phase 4): the daily prices, partitioned by ticker — query-first (one company's whole history in
    # one partition, ~10k rows; a synthetic row_id uuid clustering column keeps every bar unique so nothing
    # upserts away on the shared ticker key). The one net-new store for the finance domain.
    cassandra_allow={"price_daily": "ticker"},
    # Phase 3 (filings RAG): the section-aware 10-K narrative chunks embed with bge-small (384) and fan out to
    # Qdrant + Weaviate (+ LanceDB, which defaults to vector_allow). `text` is embedded; the payload carries the
    # citation fields (ticker/accn/section/chunk_id/filed) AND the chunk text itself so a retrieval hit returns
    # both the source pointer and the passage the RAG notebook answers from.
    vector_allow={
        "filings_text": {
            "text": ["text"],
            "payload": ["ticker", "accn", "section", "chunk_id", "filed", "text"],
        },
    },
    # Neo4j (Phase 2 graph): the EDGAR company graph — (:Company)-[:IN_INDUSTRY]->(:SIC) from company_meta and
    # (:Company)-[:FILED]->(:Filing) from company_filings. Company is keyed by cik so both specs MERGE onto the
    # SAME nodes (the filing spec attaches to the companies the meta spec created). FRED is tabular, not graph.
    neo4j_allow={
        # clear_labels is CRITICAL here: both specs share the :Company label (keyed by cik so they MERGE onto the
        # SAME nodes). The loader's default clear = every node label in the spec, so without an override whichever
        # graph runs SECOND would DETACH DELETE :Company and wipe the FIRST graph's Company-edges. Each spec
        # therefore clears only its OWN non-shared label — DETACH DELETE of that label still removes this spec's
        # CREATE'd edges (they hang off it), and :Company is left alone (MERGE keeps it idempotent across reruns).
        "company_meta": {
            "clear_labels": ["SIC"],
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
            "clear_labels": ["Filing"],
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
    # opensearch/lance/stream stay empty — a later phase may expand the domain.
)

(
    datasets_finance_parquet, datasets_finance_arrow, datasets_finance_avro,
    datasets_finance_lance, datasets_finance_iceberg, datasets_finance_commit,
) = build_transform_assets(FINANCE_CFG)

datasets_finance_checks = build_asset_checks(FINANCE_CFG) + build_vector_checks(FINANCE_CFG)
datasets_finance_store_assets = build_store_load_assets(FINANCE_CFG)
datasets_finance_stream_assets = build_stream_produce_assets(FINANCE_CFG)
