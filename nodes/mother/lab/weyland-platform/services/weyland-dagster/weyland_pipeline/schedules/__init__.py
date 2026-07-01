from dagster import ScheduleDefinition, define_asset_job, AssetSelection, DefaultScheduleStatus

# Serialize the dataset transforms: each format step re-reads ALL of raw/ into memory, so running the
# 5 formats concurrently meant 5× peak memory → node-level OOMKilled (no container mem limit; ~43GiB
# node already heavily committed). max_concurrent=1 runs the formats one at a time → 1× peak. (2026-06-29)
_SERIAL_EXEC = {"execution": {"config": {"multiprocess": {"max_concurrent": 1}}}}

# Ingestion = everything EXCEPT the eval and catalog groups (they have their own schedules).
# `datasets` (B72) is excluded too: it must NOT run on the 15-min cron — datasets_land re-downloads
# external sources (incl. FMA's ~342 MB zip), so it's on-demand + sensor-triggered only.
weyland_ingestion_job = define_asset_job(
    name="weyland_ingestion_job",
    selection=AssetSelection.all()
    - AssetSelection.groups("eval")
    - AssetSelection.groups("catalog")
    - AssetSelection.groups("aidlc_kb")
    - AssetSelection.groups("ai_session")
    - AssetSelection.groups("datasets_music")
    - AssetSelection.groups("datasets_health")
    - AssetSelection.groups("timeseries"),
)

# B72 — the brokered fan-out (all per-format assets, each isolated in its own process);
# triggered by the datasets_music_raw_sensor on new raw writes.
weyland_datasets_music_transform_job = define_asset_job(
    name="weyland_datasets_music_transform_job",
    config=_SERIAL_EXEC,
    selection=AssetSelection.groups("datasets_music") - AssetSelection.assets(
        "datasets_music_spotify_land",
        "datasets_music_fma_tracks_land",
        "datasets_music_fma_genres_land",
        "datasets_music_fma_echonest_land",
        "datasets_music_fma_features_land",
        "datasets_music_uci_year_prediction_land",
        "datasets_music_lastfm_land",
        "datasets_music_musicbrainz_land",
        "datasets_music_gtzan_land",
        "datasets_music_lp_musiccaps_mc_land",
        "datasets_music_lp_musiccaps_mtt_land",
        "datasets_music_audioset_land",
    ),
)

# Model catalog (hosted-model lookup table) — refreshed on its own 6h cadence, separate from ingestion.
weyland_catalog_job = define_asset_job(
    name="weyland_catalog_job",
    selection=AssetSelection.groups("catalog"),
)

# Eval (B4), triggered on demand (no schedule). Split so the expensive matrix and the
# cheaper scoring run independently — re-score a run without re-running the matrix.
weyland_eval_job = define_asset_job(
    name="weyland_eval_job",  # question-gen + run-matrix
    selection=AssetSelection.assets("eval_testset", "eval_run_matrix"),
)
weyland_eval_score_job = define_asset_job(
    name="weyland_eval_score_job",  # LLM-as-judge scoring of the latest results + Iceberg publish
    selection=AssetSelection.assets("eval_scores", "iceberg_eval_scores", "eval_mlflow_log"),
)

# AIDLC knowledge-base ingest (B37) — on-demand only (NO schedule): the corpus is static, re-run after
# re-uploading to MinIO. Kept out of weyland_ingestion_job (the 15-min cron) via the group subtraction above.
weyland_aidlc_kb_job = define_asset_job(
    name="weyland_aidlc_kb_job",
    selection=AssetSelection.groups("aidlc_kb"),
)

# B62 — AI-dev usage data product: ingest session summaries from MinIO -> Port. Scheduled (sessions
# keep updating, unlike the static aidlc-kb corpus); also runnable on demand.
weyland_ai_session_job = define_asset_job(
    name="weyland_ai_session_job",
    selection=AssetSelection.groups("ai_session"),
)

weyland_ingestion_schedule = ScheduleDefinition(
    job=weyland_ingestion_job,
    cron_schedule="0 * * * *",  # hourly (was */15 — too aggressive, competed with land jobs)
    name="weyland_ingestion_schedule",
    default_status=DefaultScheduleStatus.RUNNING,
)

weyland_catalog_schedule = ScheduleDefinition(
    job=weyland_catalog_job,
    cron_schedule="0 */6 * * *",  # every 6h
    name="weyland_catalog_schedule",
    default_status=DefaultScheduleStatus.RUNNING,
)

weyland_ai_session_schedule = ScheduleDefinition(
    job=weyland_ai_session_job,
    cron_schedule="0 */4 * * *",  # every 4h
    name="weyland_ai_session_schedule",
    default_status=DefaultScheduleStatus.RUNNING,
)

# Music domain — land all music datasets (on-demand; FMA zip is ~342MB, new B75 sources vary).
weyland_datasets_music_land_job = define_asset_job(
    name="weyland_datasets_music_land_job",
    selection=AssetSelection.assets(
        "datasets_music_spotify_land",
        "datasets_music_fma_tracks_land",
        "datasets_music_fma_genres_land",
        "datasets_music_fma_echonest_land",
        "datasets_music_fma_features_land",
        "datasets_music_uci_year_prediction_land",
        "datasets_music_lastfm_land",
        "datasets_music_musicbrainz_land",
        "datasets_music_gtzan_land",
        "datasets_music_lp_musiccaps_mc_land",
        "datasets_music_lp_musiccaps_mtt_land",
        "datasets_music_audioset_land",
    ),
)

# B65 Tier-2 — health domain: land all 8 health/wellness/personality datasets.
# Assets self-regulate via check_source_freshness — daily schedule is safe (skips fresh assets).
# Explicit list (NOT the whole group) — the group now also holds the transform/commit assets.
_HEALTH_LAND_ASSETS = (
    "datasets_health_nhanes_land",
    "datasets_health_big_five_land",
    "datasets_health_who_gho_land",
    "datasets_health_cdc_physical_activity_land",
    "datasets_health_brfss_land",
    "datasets_health_nhis_land",
    "datasets_health_usda_fooddata_land",
    "datasets_health_open_food_facts_land",
)
weyland_datasets_health_land_job = define_asset_job(
    name="weyland_datasets_health_land_job",
    selection=AssetSelection.assets(*_HEALTH_LAND_ASSETS),
)

# Health transform (silver + gold) — everything in the group EXCEPT the land assets:
# datasets_health_parquet / _arrow / _avro / _lance / _iceberg / _commit. On-demand.
weyland_datasets_health_transform_job = define_asset_job(
    name="weyland_datasets_health_transform_job",
    config=_SERIAL_EXEC,
    selection=AssetSelection.groups("datasets_health") - AssetSelection.assets(*_HEALTH_LAND_ASSETS),
)

# Store hydration (data-store-mageddon) — silver Parquet → Tier-2 stores. Own group (datasets_health_stores)
# so the transform job never runs it; gated by the parquet no_failures check (loader deps on _parquet).
weyland_datasets_health_hydrate_job = define_asset_job(
    name="weyland_datasets_health_hydrate_job",
    selection=AssetSelection.groups("datasets_health_stores"),
)

weyland_datasets_music_land_schedule = ScheduleDefinition(
    job=weyland_datasets_music_land_job,
    cron_schedule="0 3 * * *",  # 3 AM daily — assets self-skip if fresh (30-day window)
    name="weyland_datasets_music_land_schedule",
    default_status=DefaultScheduleStatus.STOPPED,  # enable when ready for automation
)

weyland_datasets_health_land_schedule = ScheduleDefinition(
    job=weyland_datasets_health_land_job,
    cron_schedule="0 4 * * *",  # 4 AM daily — assets self-skip if fresh (7-day window)
    name="weyland_datasets_health_land_schedule",
    default_status=DefaultScheduleStatus.STOPPED,  # enable when ready for automation
)

# B65 Tier-2 — TimescaleDB time-series writes: sync eval/guardrail/dagster/unleash/datahub → hypertables.
# Hourly is sufficient — these are analytical feeds, not real-time.
weyland_timeseries_job = define_asset_job(
    name="weyland_timeseries_job",
    selection=AssetSelection.groups("timeseries"),
)

weyland_timeseries_schedule = ScheduleDefinition(
    job=weyland_timeseries_job,
    cron_schedule="0 * * * *",  # hourly
    name="weyland_timeseries_schedule",
    default_status=DefaultScheduleStatus.RUNNING,
)
