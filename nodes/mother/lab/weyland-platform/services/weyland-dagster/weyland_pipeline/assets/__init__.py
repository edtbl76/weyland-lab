# ruff: noqa: F401 — B158-F: this __init__ re-exports every asset; the imports ARE the registration
# (autodiscovery below reads them from globals()), so 'unused import' does not apply.
from .source_document import source_document
from .content_hash import content_hash
from .rag_stream_produce import rag_stream_produce
from .eval_testset import eval_testset
from .eval_run_matrix import eval_run_matrix
from .eval_scores import eval_scores
from .model_catalog import model_catalog
from .aidlc_kb import aidlc_kb_ingest, aidlc_kb_mongo
from .ai_session import ai_session_ingest
from .iceberg_export import iceberg_model_catalog, iceberg_eval_scores
from .eval_mlflow import eval_mlflow_log
from .genre_feast_training import genre_feast_training_set
from .price_feast_training import price_feast_training_set
from .mart_export import mart_spotify_audio_export
from .datasets_music_transform import (
    datasets_music_parquet,
    datasets_music_arrow,
    datasets_music_avro,
    datasets_music_lance,
    datasets_music_iceberg,
    datasets_music_commit,
    datasets_music_checks,
    datasets_music_store_assets,
    datasets_music_stream_assets,
)
from .datasets_music_spotify_land import datasets_music_spotify_land
from .datasets_music_fma_land import (
    datasets_music_fma_tracks_land,
    datasets_music_fma_genres_land,
    datasets_music_fma_echonest_land,
)
from .datasets_music_uci_year_prediction_land import datasets_music_uci_year_prediction_land
from .datasets_music_lastfm_land import datasets_music_lastfm_land
from .datasets_music_musicbrainz_land import datasets_music_musicbrainz_land
from .datasets_music_fma_features_land import datasets_music_fma_features_land
from .datasets_music_gtzan_land import datasets_music_gtzan_land
from .datasets_music_lp_musiccaps_land import datasets_music_lp_musiccaps_mc_land, datasets_music_lp_musiccaps_mtt_land
from .datasets_music_audioset_land import datasets_music_audioset_land
from .timescaledb_write import (
    ts_eval_scores,
    ts_guardrail_verdicts,
    ts_dagster_runs,
    ts_unleash_metrics,
    ts_datahub_ingestion,
)
from .datasets_health_nhanes_land import datasets_health_nhanes_land
from .datasets_health_big_five_land import datasets_health_big_five_land
from .datasets_health_who_gho_land import datasets_health_who_gho_land
from .datasets_health_cdc_physical_activity_land import datasets_health_cdc_physical_activity_land
from .datasets_health_brfss_land import datasets_health_brfss_land
from .datasets_health_nhis_land import datasets_health_nhis_land
from .datasets_health_usda_fooddata_land import datasets_health_usda_fooddata_land
from .datasets_health_open_food_facts_land import datasets_health_open_food_facts_land
from .datasets_health_transform import (
    datasets_health_parquet,
    datasets_health_arrow,
    datasets_health_avro,
    datasets_health_lance,
    datasets_health_iceberg,
    datasets_health_commit,
    datasets_health_open_food_facts_parquet,
    datasets_health_checks,
    datasets_health_store_assets,
    datasets_health_stream_assets,
)
from .datasets_finance_fred_land import datasets_finance_fred_land
from .datasets_finance_edgar_land import datasets_finance_edgar_land
from .datasets_finance_edgar_text_land import datasets_finance_edgar_text_land
from .datasets_finance_market_land import datasets_finance_market_land
from .datasets_finance_transform import (
    datasets_finance_parquet,
    datasets_finance_arrow,
    datasets_finance_avro,
    datasets_finance_lance,
    datasets_finance_iceberg,
    datasets_finance_commit,
    datasets_finance_checks,
    datasets_finance_store_assets,
    datasets_finance_stream_assets,
)
from .registrations import (
    bifrost_prompts_registered,
    bifrost_skills_registered,
    realm_roles_registered,
    prompt_federation_synced,
    langfuse_golden_dataset,
    langfuse_codified_evals,
)

# B158 follow-up F — all_assets / all_asset_checks are DERIVED from the imports above, not hand-listed.
# The old hand-maintained lists were a SECOND registration that drifted from the imports: B113's
# `datasets_finance_edgar_land` was imported but left out of `all_assets`, so it silently did not load.
# Now the import IS the registration. Every imported `AssetsDefinition` (and every imported list of them —
# the store/stream factory results) joins `all_assets`; every imported `*_checks` list (the per-domain
# build_asset_checks results) joins `all_asset_checks`. Verified 2026-09-05 to reproduce the previous
# explicit lists exactly (the imports were already 1:1 with `all_assets`). The registration is guarded by
# tests/test_asset_registration.py (a land asset that is not imported fails CI), and a wrong derived set
# fails the dagster code-server load loudly, never silently. `all_asset_checks` is collected by NAME rather
# than by isinstance so a mis-typed check can never silently empty the quality gate.
from dagster import AssetsDefinition

all_assets = []
for _v in list(globals().values()):
    if isinstance(_v, AssetsDefinition):
        all_assets.append(_v)
    elif isinstance(_v, (list, tuple)) and _v and all(isinstance(_x, AssetsDefinition) for _x in _v):
        all_assets.extend(_v)

all_asset_checks = []
for _name, _v in list(globals().items()):
    if _name.endswith("_checks") and isinstance(_v, (list, tuple)):
        all_asset_checks.extend(_v)
