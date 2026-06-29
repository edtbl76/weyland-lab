import os
from dagster import Definitions, ScheduleDefinition, job, op, DefaultScheduleStatus
from weyland_pipeline.assets import all_assets
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
    weyland_timeseries_job,
    weyland_timeseries_schedule,
)
from weyland_pipeline.sensors import datasets_music_raw_sensor

# DataHub catalog emitter — walks the asset graph and pushes datasets + lineage to GMS via
# the datahub SDK (see datahub_emit.py). Replaces the acryl run_status_sensor, which is dead
# on Dagster 1.13 (dagster#21526). Idempotent; scheduled hourly. Reads DATAHUB_GMS_TOKEN.
# One op per emitter so each shows as its own step in the Dagster run graph + logs (via context.log →
# structured run log, NOT print → stdout tab) exactly what landed in DataHub and where.
@op
def emit_dagster_assets_op(context):
    from weyland_pipeline.datahub_emit import emit

    context.log.info(f"✓ Dagster assets → DataHub: {emit()} datasets (platform=dagster)")


@op
def emit_qdrant_op(context):
    from weyland_pipeline.datahub_emit import emit_qdrant

    n, names = emit_qdrant()
    context.log.info(f"✓ Qdrant → DataHub: {n} collection(s) {names} (platform=qdrant, lineage ← qdrant_write)")


@op
def emit_weaviate_op(context):
    from weyland_pipeline.datahub_emit import emit_weaviate

    n, names = emit_weaviate()
    context.log.info(f"✓ Weaviate → DataHub: {n} class(es) {names} (platform=weaviate, lineage ← weaviate_write)")


@op
def emit_lakefs_op(context):
    from weyland_pipeline.datahub_emit import emit_lakefs

    n, names = emit_lakefs()
    context.log.info(f"✓ lakeFS → DataHub: {n} repo(s) {names} (platform=lakefs, lineage ← datasets_commit)")


@op
def emit_opensearch_op(context):
    from weyland_pipeline.datahub_emit import emit_opensearch

    n, names = emit_opensearch()
    context.log.info(f"✓ OpenSearch → DataHub: {n} index(es) {names} (platform=opensearch)")


@op
def emit_duckdb_op(context):
    from weyland_pipeline.datahub_emit import emit_duckdb

    n, names = emit_duckdb()
    context.log.info(f"✓ DuckDB → DataHub: {n} view(s) {names} (platform=duckdb, lineage ← parquet)")


@op
def emit_timescaledb_op(context):
    from weyland_pipeline.datahub_emit import emit_timescaledb

    n, names = emit_timescaledb()
    context.log.info(f"✓ TimescaleDB → DataHub: {n} hypertable(s) {names} (platform=timescaledb, lineage ← source tables)")


@job
def datahub_catalog_emit_job():
    emit_dagster_assets_op()
    emit_qdrant_op()
    emit_weaviate_op()
    emit_lakefs_op()
    emit_opensearch_op()
    emit_duckdb_op()
    emit_timescaledb_op()


datahub_catalog_emit_schedule = ScheduleDefinition(
    job=datahub_catalog_emit_job,
    cron_schedule="0 * * * *",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=all_assets,
    jobs=[weyland_ingestion_job, weyland_eval_job, weyland_eval_score_job, weyland_catalog_job, weyland_aidlc_kb_job, weyland_ai_session_job, datahub_catalog_emit_job, weyland_datasets_music_transform_job, weyland_datasets_music_land_job, weyland_datasets_health_land_job, weyland_timeseries_job],
    schedules=[weyland_ingestion_schedule, weyland_catalog_schedule, weyland_ai_session_schedule, datahub_catalog_emit_schedule, weyland_timeseries_schedule],
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
