from dagster import ScheduleDefinition, define_asset_job, AssetSelection

# Ingestion = everything EXCEPT the eval group, so the 15-min schedule never runs eval.
weyland_ingestion_job = define_asset_job(
    name="weyland_ingestion_job",
    selection=AssetSelection.all() - AssetSelection.groups("eval"),
)

# Eval (B4), triggered on demand (no schedule). Split so the expensive matrix and the
# cheaper scoring run independently — re-score a run without re-running the matrix.
weyland_eval_job = define_asset_job(
    name="weyland_eval_job",  # question-gen + run-matrix
    selection=AssetSelection.assets("eval_testset", "eval_run_matrix"),
)
weyland_eval_score_job = define_asset_job(
    name="weyland_eval_score_job",  # LLM-as-judge scoring of the latest results
    selection=AssetSelection.assets("eval_scores"),
)

weyland_ingestion_schedule = ScheduleDefinition(
    job=weyland_ingestion_job,
    cron_schedule="*/15 * * * *",
    name="weyland_ingestion_schedule",
)
