"""Event-triggered LanceDB → viewer sync. The Lance tables (on the lakeFS S3 gateway) change ONLY when a
`datasets_<dom>_lancedb_load` asset runs — so instead of polling, a multi-asset sensor watches those two assets
and, on a new materialization, launches the `lancedb-sync` mc-mirror Job in data-mesh (lakeFS S3 → the viewer
PVC). The Job is created from the existing CronJob's template (like `kubectl create job --from=cronjob`), so the
mirror logic lives in one place. The 6h CronJob stays as a safety-net backfill. Needs RBAC (the dagster SA →
get cronjobs + create jobs in data-mesh) — k8s/data-mesh/lancedb-sync-rbac.yaml."""
from dagster import (
    AssetKey,
    DefaultSensorStatus,
    RunRequest,
    SkipReason,
    job,
    multi_asset_sensor,
    op,
)


@op
def trigger_lancedb_sync(context):
    """Create a Job in data-mesh from the lancedb-sync CronJob's jobTemplate (in-cluster API)."""
    from kubernetes import client, config

    config.load_incluster_config()
    batch = client.BatchV1Api()
    cj = batch.read_namespaced_cron_job("lancedb-sync", "data-mesh")
    name = f"lancedb-sync-{context.run_id[:8]}"
    job_spec = cj.spec.job_template.spec
    job_spec.ttl_seconds_after_finished = 600   # self-clean these ad-hoc jobs
    batch.create_namespaced_job(
        "data-mesh",
        client.V1Job(metadata=client.V1ObjectMeta(name=name, namespace="data-mesh"), spec=job_spec),
    )
    context.log.info(f"launched sync Job {name} in data-mesh (lakeFS Lance tables → viewer PVC)")


@job
def weyland_lancedb_sync_job():
    trigger_lancedb_sync()


@multi_asset_sensor(
    monitored_assets=[AssetKey("datasets_music_lancedb_load"), AssetKey("datasets_health_lancedb_load")],
    job=weyland_lancedb_sync_job,
    default_status=DefaultSensorStatus.RUNNING,
)
def lancedb_sync_sensor(context):
    """Fire the sync job when either lancedb load has a new materialization."""
    records = context.latest_materialization_records_by_key()
    if any(v is not None for v in records.values()):
        context.advance_all_cursors()
        return RunRequest()
    return SkipReason("no new lancedb materialization")
