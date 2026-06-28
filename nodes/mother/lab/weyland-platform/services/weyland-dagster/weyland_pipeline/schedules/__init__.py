from dagster import ScheduleDefinition, define_asset_job, AssetSelection, DefaultScheduleStatus

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
    - AssetSelection.groups("datasets")
    - AssetSelection.groups("timeseries"),
)

# B72 — the brokered fan-out (all five per-format assets, each isolated in its own process);
# triggered by the datasets_raw S3 sensor on new raw writes. = the datasets group minus the loader.
weyland_datasets_transform_job = define_asset_job(
    name="weyland_datasets_transform_job",
    selection=AssetSelection.groups("datasets") - AssetSelection.assets("datasets_land"),
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
    cron_schedule="*/15 * * * *",
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
