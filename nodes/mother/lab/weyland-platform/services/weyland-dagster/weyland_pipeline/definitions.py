import os
from dagster import Definitions, ScheduleDefinition, job, op, DefaultScheduleStatus
from weyland_pipeline.assets import all_assets, all_asset_checks
from weyland_pipeline.resources import (
    PostgresResource,
    SentenceTransformerResource,
    QdrantResource,
    WeaviateResource,
    Neo4jResource,
)
from weyland_pipeline.schedules import (
    weyland_ingestion_schedule,
    weyland_ingestion_job,
    weyland_eval_job,
    weyland_eval_score_job,
    weyland_catalog_job,
    weyland_catalog_schedule,
    weyland_aidlc_kb_job,
    weyland_ai_session_job,
    weyland_ai_session_schedule,
    weyland_datasets_music_transform_job,
    weyland_datasets_music_land_job,
    weyland_datasets_health_land_job,
    weyland_datasets_health_transform_job,
    weyland_datasets_health_hydrate_job,
    weyland_datasets_music_land_schedule,
    weyland_datasets_health_land_schedule,
    weyland_timeseries_job,
    weyland_timeseries_schedule,
)
from weyland_pipeline.sensors import datasets_music_raw_sensor

# DataHub catalog emitter — walks the asset graph and pushes datasets + lineage to GMS via
# the datahub SDK (see datahub_emit.py). Replaces the acryl run_status_sensor, which is dead
# on Dagster 1.13 (dagster#21526). Idempotent; scheduled hourly. Reads DATAHUB_GMS_TOKEN.
# One op per emitter so each shows as its own step in the Dagster run graph + logs (via context.log →
# structured run log, NOT print → stdout tab) exactly what landed in DataHub and where.
def _safe_emit(context, label, emit_fn):
    """Run one store's emitter, swallowing failures so a single flaky store (Qdrant timing out, a store
    restarting) logs a WARNING and is skipped — the whole nightly catalog run doesn't fail, and the other
    stores still emit. Was the missing piece: one Qdrant read-timeout failed the entire catalog job."""
    try:
        context.log.info(f"✓ {label} → DataHub: {emit_fn()}")
    except Exception as e:  # noqa: BLE001 — one flaky store must not sink the catalog run
        context.log.warning(f"⚠ {label} → DataHub emit SKIPPED (failed, run continues): {e}")


@op
def emit_dagster_assets_op(context):
    from weyland_pipeline.datahub_emit import emit
    _safe_emit(context, "Dagster assets", emit)


@op
def emit_qdrant_op(context):
    from weyland_pipeline.datahub_emit import emit_qdrant
    _safe_emit(context, "Qdrant", emit_qdrant)


@op
def emit_weaviate_op(context):
    from weyland_pipeline.datahub_emit import emit_weaviate
    _safe_emit(context, "Weaviate", emit_weaviate)


@op
def emit_lakefs_op(context):
    from weyland_pipeline.datahub_emit import emit_lakefs
    _safe_emit(context, "lakeFS", emit_lakefs)


@op
def emit_opensearch_op(context):
    from weyland_pipeline.datahub_emit import emit_opensearch
    _safe_emit(context, "OpenSearch", emit_opensearch)


@op
def emit_duckdb_op(context):
    from weyland_pipeline.datahub_emit import emit_duckdb
    _safe_emit(context, "DuckDB", emit_duckdb)


@op
def emit_timescaledb_op(context):
    from weyland_pipeline.datahub_emit import emit_timescaledb
    _safe_emit(context, "TimescaleDB", emit_timescaledb)


@op
def emit_mysql_op(context):
    from weyland_pipeline.datahub_emit import emit_mysql
    _safe_emit(context, "MySQL", emit_mysql)


@job
def datahub_catalog_emit_job():
    emit_dagster_assets_op()
    emit_qdrant_op()
    emit_weaviate_op()
    emit_lakefs_op()
    emit_opensearch_op()
    emit_duckdb_op()
    emit_timescaledb_op()
    emit_mysql_op()


datahub_catalog_emit_schedule = ScheduleDefinition(
    job=datahub_catalog_emit_job,
    cron_schedule="40 */6 * * *",  # every 6h at :40 (was hourly-on-:00 — stampeded mother with the other jobs)
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=all_assets,
    asset_checks=all_asset_checks,
    jobs=[weyland_ingestion_job, weyland_eval_job, weyland_eval_score_job, weyland_catalog_job, weyland_aidlc_kb_job, weyland_ai_session_job, datahub_catalog_emit_job, weyland_datasets_music_transform_job, weyland_datasets_music_land_job, weyland_datasets_health_land_job, weyland_datasets_health_transform_job, weyland_datasets_health_hydrate_job, weyland_timeseries_job],
    schedules=[weyland_ingestion_schedule, weyland_catalog_schedule, weyland_ai_session_schedule, datahub_catalog_emit_schedule, weyland_timeseries_schedule, weyland_datasets_music_land_schedule, weyland_datasets_health_land_schedule],
    sensors=[datasets_music_raw_sensor],
    resources={
        "postgres": PostgresResource(
            host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
            port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
            dbname=os.environ.get("WEYLAND_PG_DB", "weyland"),
            user=os.environ.get("WEYLAND_PG_USER", "weyland"),
            password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
        ),
        "sentence_transformer": SentenceTransformerResource(),
        "qdrant": QdrantResource(
            host=os.environ.get("QDRANT_HOST", "qdrant.weyland.svc.cluster.local"),
            port=int(os.environ.get("QDRANT_PORT", "6333")),
        ),
        "weaviate": WeaviateResource(
            host=os.environ.get("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local"),
            port=int(os.environ.get("WEAVIATE_PORT", "8080")),
            grpc_port=int(os.environ.get("WEAVIATE_GRPC_PORT", "50051")),
        ),
        "neo4j": Neo4jResource(
            uri=os.environ.get("NEO4J_URI", "bolt://neo4j.weyland.svc.cluster.local:7687"),
            user=os.environ.get("NEO4J_USER", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", ""),
        ),
    },
)
