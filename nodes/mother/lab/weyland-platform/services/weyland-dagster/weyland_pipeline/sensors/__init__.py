"""B72 step 3 — S3 sensor: trigger the fan-out transform when new raw data lands.

A PLAIN polling sensor (cursor over the MinIO raw/ listing) — NOT a run_status_sensor (that one is
dead on Dagster 1.13, dagster#21526). Ships STOPPED: enable it in the Dagster UI (Automation) only
after datasets_land + datasets_transform are proven green, so it never spams failed runs.
"""
import os

from dagster import DefaultSensorStatus, RunRequest, SkipReason, sensor

from weyland_pipeline.schedules import weyland_datasets_transform_job


@sensor(
    job=weyland_datasets_transform_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.STOPPED,
)
def datasets_raw_sensor(context):
    from minio import Minio

    client = Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")

    latest = None  # the newest raw CSV write seen this poll (max last_modified)
    for obj in client.list_objects(bucket, prefix="raw/", recursive=True):
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
