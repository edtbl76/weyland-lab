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
    weyland_datasets_transform_job,
)
from weyland_pipeline.sensors import datasets_raw_sensor

# DataHub catalog emitter — walks the asset graph and pushes datasets + lineage to GMS via
# the datahub SDK (see datahub_emit.py). Replaces the acryl run_status_sensor, which is dead
# on Dagster 1.13 (dagster#21526). Idempotent; scheduled hourly. Reads DATAHUB_GMS_TOKEN.
@op
def emit_datahub_catalog_op():
    from weyland_pipeline.datahub_emit import emit

    emit()


@job
def datahub_catalog_emit_job():
    emit_datahub_catalog_op()


datahub_catalog_emit_schedule = ScheduleDefinition(
    job=datahub_catalog_emit_job,
    cron_schedule="0 * * * *",
    default_status=DefaultScheduleStatus.RUNNING,
)

defs = Definitions(
    assets=all_assets,
    jobs=[weyland_ingestion_job, weyland_eval_job, weyland_eval_score_job, weyland_catalog_job, weyland_aidlc_kb_job, weyland_ai_session_job, datahub_catalog_emit_job, weyland_datasets_transform_job],
    schedules=[weyland_ingestion_schedule, weyland_catalog_schedule, weyland_ai_session_schedule, datahub_catalog_emit_schedule],
    sensors=[datasets_raw_sensor],
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
