"""Health dataset fan-out transform — the explicit health DomainConfig over the shared broker.

Same mechanism as music (datasets_lib): the only health specifics are the repo, namespace, the multi-format
reader (the shared reader already dispatches .xpt/.json/.csv.gz), and the allowlists. build_transform_assets()
produces datasets_health_parquet/_arrow/_avro/_lance/_iceberg + _commit."""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks, build_vector_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.streaming import build_streamed_parquet_asset
from .datasets_lib.streaming_producer import build_stream_produce_assets

# open_food_facts is DEFERRED from the inline broker (its ~9GB-decompressed, 211-column TSV OOMs the whole-
# table read). It gets its silver PARQUET from a dedicated STREAMING asset instead
# (datasets_health_open_food_facts_parquet, below); the broker's other formats (arrow/avro/lance/iceberg)
# stay deferred for a source this size — parquet is what the store loaders read.
_DEFERRED = frozenset({"open_food_facts"})
_ALL = frozenset({
    "nhanes", "big_five", "who_gho", "cdc_physical_activity",
    "brfss", "nhis", "usda_fooddata", "open_food_facts",
}) - _DEFERRED
_LANCE = frozenset({"big_five", "usda_fooddata", "open_food_facts"}) - _DEFERRED

HEALTH_CFG = DomainConfig(
    domain="health",
    repo="health",
    namespace="datasets_health",
    group_name="datasets_health",
    land_deps=(
        "datasets_health_nhanes_land", "datasets_health_big_five_land", "datasets_health_who_gho_land",
        "datasets_health_cdc_physical_activity_land", "datasets_health_brfss_land",
        "datasets_health_nhis_land", "datasets_health_usda_fooddata_land", "datasets_health_open_food_facts_land",
    ),
    parquet_allow=_ALL, arrow_allow=_ALL, avro_allow=_ALL, iceberg_allow=_ALL,
    lance_allow=_LANCE,
    # Store hydration (grid MySQL=Y): the 6 health datasets MySQL targets (usda/open_food_facts are N).
    mysql_allow=frozenset({"nhanes", "big_five", "who_gho", "cdc_physical_activity", "brfss", "nhis"}),
    # TimescaleDB (grid): WHO GHO only — country/year series. Time axis derived from TimeDim (the year).
    # Last.fm (grid=Y "listening trends") is intentionally SKIPPED: its silver is lifetime user↔artist
    # playcounts with no per-listen timestamps, so it isn't a real time-series (only signup_date is temporal).
    timescale_allow={"who_gho": "TimeDim"},
    # MongoDB (grid): WHO GHO (nested JSON) + Open Food Facts (doc per product). OFF's silver comes from
    # the streamed asset (below), so the Mongo loader deps on it via streamed_parquet.
    mongo_allow=frozenset({"who_gho", "open_food_facts"}),
    streamed_parquet=frozenset({"open_food_facts"}),
    # CockroachDB (grid): BRFSS + NHIS (US health survey — "geo-partitioned" intent; single-node lab loads
    # the tables, real geo-partitioning would need a multi-node cluster).
    cockroach_allow=frozenset({"brfss", "nhis"}),
    # Cassandra (grid=Y): big_five + who_gho. Partition key = a natural column (query-first): who_gho by
    # SpatialDim (country) — the country/year series; big_five by country. Names are sanitized to match the
    # silver columns; if a guess is wrong the loader falls back to a row_id dump and logs the real columns.
    cassandra_allow={"big_five": "country", "who_gho": "SpatialDim"},
    # ClickHouse (grid=Y, "search"/analytics): usda_fooddata + open_food_facts (OFF's silver = streamed asset).
    clickhouse_allow=frozenset({"usda_fooddata", "open_food_facts"}),
    # OpenSearch (grid=Y, similarity search): big_five (profile) + open_food_facts (product). Doc-per-row index.
    opensearch_allow=frozenset({"big_five", "open_food_facts"}),
    # Qdrant + Weaviate (grid=Y): big_five personality vector — the 50 OCEAN items (E*/N*/A*/C*/O*), z-scored;
    # demographics excluded. open_food_facts → B78 (4.5M docs, capped embed = maturity/polish).
    # vector_allow feeds Qdrant, Weaviate AND LanceDB: lancedb_allow is unset, so LanceDB inherits this
    # set (loaders.py:1153, `cfg.lancedb_allow or cfg.vector_allow`). Both entries INTENTIONALLY hydrate
    # all three — big_five and OFF each get cross-store presence and LanceDB is embedded on object
    # storage (cheap, no server). To keep OFF out of LanceDB, set lancedb_allow={"big_five": ...}
    # EXPLICITLY (dropping it here would also drop big_five).
    vector_allow={
        "big_five": {"numeric_exclude": ["race", "age", "engnat", "gender", "hand", "source"],
                     "payload": ["country"]},
        # B78 (EMA-69) — the 4.5M-doc set, hydrated via the bounded projected+capped read in
        # _build_vectors that `cap`+`filter` switch on (loaders.py). Columns confirmed against the REAL
        # silver 2026-08-31: categories_en IS present (categories_fr is NOT — the field docs are stale);
        # id `code` is the barcode. The read projects only these ~5 of 211 columns and caps at 200k rows.
        "open_food_facts": {"text": ["product_name", "brands", "categories_en"],
                            "filter": "product_name", "cap": 200_000,
                            "id": "code", "payload": ["product_name", "brands", "url"]},
    },
    # Redpanda (grid=Y, survey streams): big_five / brfss / nhis survey responses → Avro topics. No natural key
    # (round-robin partitions). big_five is small (~20k, no cap); brfss/nhis are big → capped 100k for the demo.
    stream_allow={
        "big_five": {"key": None, "cap": None},
        "brfss": {"key": None, "cap": 100_000},
        "nhis": {"key": None, "cap": 100_000},
    },
)

(
    datasets_health_parquet, datasets_health_arrow, datasets_health_avro,
    datasets_health_lance, datasets_health_iceberg, datasets_health_commit,
) = build_transform_assets(HEALTH_CFG)

# open_food_facts silver parquet via the streamed path (broker can't read the 211-col TSV whole).
datasets_health_open_food_facts_parquet = build_streamed_parquet_asset(
    HEALTH_CFG, "open_food_facts", "products.csv.gz", sep="\t")

datasets_health_checks = build_asset_checks(HEALTH_CFG) + build_vector_checks(HEALTH_CFG)
datasets_health_store_assets = build_store_load_assets(HEALTH_CFG)
datasets_health_stream_assets = build_stream_produce_assets(HEALTH_CFG)
