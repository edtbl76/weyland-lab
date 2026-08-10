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
from .registrations import (
    bifrost_prompts_registered,
    bifrost_skills_registered,
    realm_roles_registered,
    prompt_federation_synced,
)

all_assets = [
    source_document,
    content_hash,
    rag_stream_produce,
    eval_testset,
    eval_run_matrix,
    eval_scores,
    model_catalog,
    aidlc_kb_ingest,
    aidlc_kb_mongo,
    ai_session_ingest,
    iceberg_model_catalog,
    iceberg_eval_scores,
    eval_mlflow_log,
    genre_feast_training_set,
    mart_spotify_audio_export,
    # Music domain — per-dataset land assets
    datasets_music_spotify_land,
    datasets_music_fma_tracks_land,
    datasets_music_fma_genres_land,
    datasets_music_fma_echonest_land,
    datasets_music_uci_year_prediction_land,
    datasets_music_lastfm_land,
    datasets_music_musicbrainz_land,
    datasets_music_fma_features_land,
    datasets_music_gtzan_land,
    datasets_music_lp_musiccaps_mc_land,
    datasets_music_lp_musiccaps_mtt_land,
    datasets_music_audioset_land,
    # Music domain — transform (silver + gold)
    datasets_music_parquet,
    datasets_music_arrow,
    datasets_music_avro,
    datasets_music_lance,
    datasets_music_iceberg,
    datasets_music_commit,
    # TimescaleDB time-series feeds
    ts_eval_scores,
    ts_guardrail_verdicts,
    ts_dagster_runs,
    ts_unleash_metrics,
    ts_datahub_ingestion,
    # Health domain — per-dataset land assets
    datasets_health_nhanes_land,
    datasets_health_big_five_land,
    datasets_health_who_gho_land,
    datasets_health_cdc_physical_activity_land,
    datasets_health_brfss_land,
    datasets_health_nhis_land,
    datasets_health_usda_fooddata_land,
    datasets_health_open_food_facts_land,
    # Health domain — transform (silver + gold)
    datasets_health_parquet,
    datasets_health_arrow,
    datasets_health_avro,
    datasets_health_lance,
    datasets_health_iceberg,
    datasets_health_commit,
    datasets_health_open_food_facts_parquet,   # streamed silver (broker can't read the 9GB TSV whole)
    # Health domain — store hydration (data-store-mageddon)
    *datasets_health_store_assets,
    *datasets_music_store_assets,
    *datasets_health_stream_assets,
    *datasets_music_stream_assets,
    # B102 — registrations reconcile (Bifrost prompt/skill repos + Realm role prompts)
    bifrost_prompts_registered,
    bifrost_skills_registered,
    realm_roles_registered,
    prompt_federation_synced,
]

# Pre-hydration quality gate (build_asset_checks per domain — the second datasets_lib factory)
all_asset_checks = [*datasets_music_checks, *datasets_health_checks]
