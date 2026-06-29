"""Sensors for the weyland pipeline.

datasets_music_raw_sensor — triggers music transform when new raw files land in lakeFS

Note: freshness is handled in-asset (each land asset self-skips when fresh via
check_source_freshness / is_fresh_local) + the daily land schedules. The old
freshness sensors were redundant and were removed.
"""
import os

from dagster import DefaultSensorStatus, RunRequest, SkipReason, sensor

from weyland_pipeline.schedules import weyland_datasets_music_transform_job


@sensor(
    job=weyland_datasets_music_transform_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.STOPPED,
)
def datasets_music_raw_sensor(context):
    from minio import Minio

    client = Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    domain = os.environ.get("DATASETS_DOMAIN", "music")

    latest = None
    for obj in client.list_objects(bucket, prefix=f"{domain}/raw/", recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        stamp = obj.last_modified.isoformat() if obj.last_modified else obj.object_name
        if latest is None or stamp > latest:
            latest = stamp

    if latest is None:
        return SkipReason("no raw CSVs yet")
    if context.cursor == latest:
        return SkipReason("no new raw writes since last run")
    context.update_cursor(latest)
    return RunRequest(run_key=latest)
