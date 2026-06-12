from dagster import ScheduleDefinition, define_asset_job, AssetSelection

# Ingestion = everything EXCEPT the eval group, so the 15-min schedule never runs eval.
weyland_ingestion_job = define_asset_job(
    name="weyland_ingestion_job",
    selection=AssetSelection.all() - AssetSelection.groups("eval"),
)

# Eval (B4) = the eval group only, triggered on demand (no schedule).
weyland_eval_job = define_asset_job(
    name="weyland_eval_job",
    selection=AssetSelection.groups("eval"),
)

weyland_ingestion_schedule = ScheduleDefinition(
    job=weyland_ingestion_job,
    cron_schedule="*/15 * * * *",
    name="weyland_ingestion_schedule",
)
