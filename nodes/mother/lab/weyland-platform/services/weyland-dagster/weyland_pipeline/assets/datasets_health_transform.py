"""Health dataset fan-out transform — the explicit health DomainConfig over the shared broker.

Same mechanism as music (datasets_lib): the only health specifics are the repo, namespace, the multi-format
reader (the shared reader already dispatches .xpt/.json/.csv.gz), and the allowlists. build_transform_assets()
produces datasets_health_parquet/_arrow/_avro/_lance/_iceberg + _commit."""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.config import DomainConfig

# open_food_facts is DEFERRED from the inline broker: its raw is a ~9GB .csv.gz, and reading it whole-file
# hung the arrow step past the 1h timeout. It needs a dedicated chunked/streaming asset (backlog). Drop it
# from _DEFERRED to re-enable.
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
)

(
    datasets_health_parquet, datasets_health_arrow, datasets_health_avro,
    datasets_health_lance, datasets_health_iceberg, datasets_health_commit,
) = build_transform_assets(HEALTH_CFG)
