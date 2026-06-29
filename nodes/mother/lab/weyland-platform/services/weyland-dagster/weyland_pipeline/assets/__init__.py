from .source_document import source_document
from .content_hash import content_hash
from .hash_check import hash_check
from .chunks import chunks
from .embeddings import embeddings
from .pgvector_write import pgvector_write
from .qdrant_write import qdrant_write
from .weaviate_write import weaviate_write
from .neo4j_write import neo4j_write
from .opensearch_write import opensearch_write
from .eval_testset import eval_testset
from .eval_run_matrix import eval_run_matrix
from .eval_scores import eval_scores
from .model_catalog import model_catalog
from .aidlc_kb import aidlc_kb_ingest
from .ai_session import ai_session_ingest
from .iceberg_export import iceberg_model_catalog, iceberg_eval_scores
from .eval_mlflow import eval_mlflow_log
from .datasets_music_transform import (
    datasets_music_parquet,
    datasets_music_arrow,
    datasets_music_avro,
    datasets_music_lance,
    datasets_music_iceberg,
    datasets_music_commit,
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

all_assets = [
    source_document,
    content_hash,
    hash_check,
    chunks,
    embeddings,
    pgvector_write,
    qdrant_write,
    weaviate_write,
    neo4j_write,
    opensearch_write,
    eval_testset,
    eval_run_matrix,
    eval_scores,
    model_catalog,
    aidlc_kb_ingest,
    ai_session_ingest,
    iceberg_model_catalog,
    iceberg_eval_scores,
    eval_mlflow_log,
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
]
