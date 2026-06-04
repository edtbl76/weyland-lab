import os
from dagster import Definitions
from weyland_pipeline.assets import all_assets
from weyland_pipeline.resources import PostgresResource, SentenceTransformerResource
from weyland_pipeline.schedules import weyland_ingestion_schedule, weyland_ingestion_job

defs = Definitions(
    assets=all_assets,
    jobs=[weyland_ingestion_job],
    schedules=[weyland_ingestion_schedule],
    resources={
        "postgres": PostgresResource(
            host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
            port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
            dbname=os.environ.get("WEYLAND_PG_DB", "weyland"),
            user=os.environ.get("WEYLAND_PG_USER", "weyland"),
            password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
        ),
        "sentence_transformer": SentenceTransformerResource(),
    },
)
