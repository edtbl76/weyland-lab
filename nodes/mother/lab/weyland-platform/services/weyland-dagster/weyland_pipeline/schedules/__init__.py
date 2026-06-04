from dagster import ScheduleDefinition, define_asset_job, AssetSelection

weyland_ingestion_job = define_asset_job(
    name="weyland_ingestion_job",
    selection=AssetSelection.all(),
)

weyland_ingestion_schedule = ScheduleDefinition(
    job=weyland_ingestion_job,
    cron_schedule="*/15 * * * *",
    name="weyland_ingestion_schedule",
)
