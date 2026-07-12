import os
from dagster import Definitions, ScheduleDefinition, job, op, DefaultScheduleStatus
from weyland_pipeline.assets import all_assets, all_asset_checks
from weyland_pipeline.dbt_assets import weyland_dbt_assets, dbt_resource
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
    weyland_datasets_music_hydrate_job,
    weyland_datasets_music_land_schedule,
    weyland_datasets_health_land_schedule,
    weyland_timeseries_job,
    weyland_timeseries_schedule,
    weyland_dbt_job,
    weyland_dbt_schedule,
)
from weyland_pipeline.sensors import datasets_music_raw_sensor
from weyland_pipeline.lancedb_sync import weyland_lancedb_sync_job, lancedb_sync_sensor

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


@op
def emit_lancedb_op(context):
    from weyland_pipeline.datahub_emit import emit_lancedb
    _safe_emit(context, "LanceDB", emit_lancedb)


@op
def emit_dbt_op(context):
    from weyland_pipeline.datahub_emit import emit_dbt
    _safe_emit(context, "dbt marts", emit_dbt)


@op
def emit_feast_op(context):
    from weyland_pipeline.datahub_emit import emit_feast
    _safe_emit(context, "Feast sources (mart lineage)", emit_feast)


@op
def emit_lightdash_op(context):
    from weyland_pipeline.datahub_emit import emit_lightdash
    _safe_emit(context, "Lightdash (BI charts + dashboards)", emit_lightdash)


@op
def emit_domains_op(context):
    from weyland_pipeline.datahub_emit import emit_domains
    _safe_emit(context, "Domains (create + auto-assign)", emit_domains)


@op
def emit_data_products_op(context):
    from weyland_pipeline.datahub_emit import emit_data_products
    _safe_emit(context, "Data Products (mesh bundles)", emit_data_products)


@op
def emit_glossary_op(context):
    from weyland_pipeline.datahub_emit import emit_glossary
    _safe_emit(context, "Business Glossary (AIDLC KB taxonomy)", emit_glossary)


@op
def emit_mesh_glossary_op(context):
    from weyland_pipeline.datahub_emit import emit_mesh_glossary
    _safe_emit(context, "Mesh Glossary (data vocab + field attach)", emit_mesh_glossary)


@op
def emit_field_docs_op(context):
    from weyland_pipeline.datahub_emit import emit_field_docs
    _safe_emit(context, "Field docs (source field dictionaries → per-column descriptions)", emit_field_docs)


@op
def emit_source_terms_op(context):
    from weyland_pipeline.datahub_emit import emit_source_terms
    _safe_emit(context, "Source terms (external citations + description-based term attach)", emit_source_terms)


@op
def emit_structured_properties_op(context):
    from weyland_pipeline.datahub_emit import emit_structured_properties
    _safe_emit(context, "Structured Properties (layer/source/tier facets)", emit_structured_properties)


@op
def emit_docs_links_op(context):
    from weyland_pipeline.datahub_emit import emit_docs_links
    _safe_emit(context, "Docs Links (dataset → runbook + tools)", emit_docs_links)


@op
def emit_tags_op(context):
    from weyland_pipeline.datahub_emit import emit_tags
    _safe_emit(context, "Tags (materialize layer/tier/source/field-class tag entities)", emit_tags)


@op
def emit_tag_assignments_op(context):
    from weyland_pipeline.datahub_emit import emit_tag_assignments
    _safe_emit(context, "Tag assignments (layer/tier/source → datasets)", emit_tag_assignments)


@op
def emit_ownership_op(context):
    from weyland_pipeline.datahub_emit import emit_ownership
    _safe_emit(context, "Ownership (weyland group → all datasets)", emit_ownership)


@op
def emit_queries_op(context):
    from weyland_pipeline.datahub_emit import emit_queries
    _safe_emit(context, "Example queries (per mart)", emit_queries)


@op
def emit_dataset_queries_op(context):
    from weyland_pipeline.datahub_emit import emit_dataset_queries
    _safe_emit(context, "Dataset queries (schema-aware starters, lakehouse)", emit_dataset_queries)


@op
def emit_cockroachdb_profiles_op(context):
    from weyland_pipeline.datahub_emit import emit_cockroachdb_profiles
    _safe_emit(context, "CockroachDB stats (rowCount profiles — ingestion profiler emits none)", emit_cockroachdb_profiles)


@op
def soda_scan_op(context):
    """L5 Slice C — data quality. Shell out to the isolated /opt/soda-venv (soda-core's pins can't co-exist with
    dagster/dbt in the main env) and run independent contract scans over the 7 published marts AND the WHO/BRFSS
    gold sources (each is a separate Soda data source → separate `-d` invocation). Each scan's results emit to
    DataHub (assertions/profiles/contracts). Soda exit codes: 0 = all pass, 1 = warnings, 2 = check failures,
    3 = execution error. Fail the op if ANY scan is >= 2 so a broken contract surfaces as a red Dagster run."""
    import json
    import subprocess
    from dagster import Failure
    from weyland_pipeline.datahub_emit import (
        emit_data_contracts,
        emit_soda_assertions,
        emit_soda_profiles,
    )
    # (data source, results file, [check files]) — the emitters map the data source name → the right Trino schema.
    # B80 breadth: baseline.yml (row_count>0 for-each-dataset) fans across every table in each schema; the specific
    # mart/gold check files layer richer bounds on top. weyland_music added so the music silver/gold datasets get
    # covered too — not just the 4 marts.
    _bl = "/app/soda/checks/baseline.yml"
    scans = [
        ("weyland", "/tmp/soda_marts.json", ["/app/soda/checks/music.yml", "/app/soda/checks/health.yml", _bl]),
        ("weyland_music", "/tmp/soda_music.json", [_bl]),
        ("weyland_health", "/tmp/soda_gold.json", ["/app/soda/checks/health_gold.yml", _bl]),
    ]
    worst = 0
    for ds, results_file, check_files in scans:
        cmd = ["/opt/soda-venv/bin/soda", "scan", "-d", ds, "-c", "/app/soda/configuration.yml",
               "-srf", results_file, *check_files]
        context.log.info("Running: " + " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            context.log.info(result.stdout)
        if result.stderr:
            context.log.warning(result.stderr)
        worst = max(worst, result.returncode)
        # Emit BEFORE the fail check so failing checks still surface in the catalog. Non-fatal per scan.
        try:
            with open(results_file) as f:
                scan_results = json.load(f)
            context.log.info(f"DataHub [{ds}]: {emit_soda_assertions(scan_results)} assertions, "
                             f"{emit_soda_profiles(scan_results)} profiles (Stats), "
                             f"{emit_data_contracts(scan_results)} contracts")
        except Exception as e:
            context.log.warning(f"DataHub quality emit skipped for {ds} (non-fatal): {e}")
    if worst >= 2:
        raise Failure(description=f"Soda scan failed (exit {worst}) — a table violated its data contract.")
    return worst


@job
def soda_quality_job():
    soda_scan_op()


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
    emit_lancedb_op()
    emit_dbt_op()
    emit_feast_op()
    emit_lightdash_op()
    emit_domains_op()
    emit_data_products_op()
    emit_glossary_op()
    emit_mesh_glossary_op()
    emit_field_docs_op()
    emit_source_terms_op()
    emit_structured_properties_op()
    emit_docs_links_op()
    emit_tags_op()
    emit_tag_assignments_op()
    emit_ownership_op()
    emit_queries_op()
    emit_dataset_queries_op()
    emit_cockroachdb_profiles_op()


datahub_catalog_emit_schedule = ScheduleDefinition(
    job=datahub_catalog_emit_job,
    cron_schedule="40 */6 * * *",  # every 6h at :40 (was hourly-on-:00 — stampeded mother with the other jobs)
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.RUNNING,
)

# L5 Slice C — daily data-quality scan of the marts. STOPPED by default: enable it in the Dagster UI once a
# manual soda_quality_job run passes, so it doesn't red-flag nightly before the marts/connection are verified.
soda_quality_schedule = ScheduleDefinition(
    job=soda_quality_job,
    cron_schedule="30 5 * * *",  # daily 05:30, after the nightly dbt build has republished the marts
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.STOPPED,
)

defs = Definitions(
    assets=[*all_assets, weyland_dbt_assets],
    asset_checks=all_asset_checks,
    jobs=[weyland_ingestion_job, weyland_eval_job, weyland_eval_score_job, weyland_catalog_job, weyland_aidlc_kb_job, weyland_ai_session_job, datahub_catalog_emit_job, weyland_datasets_music_transform_job, weyland_datasets_music_land_job, weyland_datasets_health_land_job, weyland_datasets_health_transform_job, weyland_datasets_health_hydrate_job, weyland_datasets_music_hydrate_job, weyland_timeseries_job, weyland_lancedb_sync_job, weyland_dbt_job, soda_quality_job],
    schedules=[weyland_ingestion_schedule, weyland_catalog_schedule, weyland_ai_session_schedule, datahub_catalog_emit_schedule, weyland_timeseries_schedule, weyland_datasets_music_land_schedule, weyland_datasets_health_land_schedule, weyland_dbt_schedule, soda_quality_schedule],
    sensors=[datasets_music_raw_sensor, lancedb_sync_sensor],
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
        "dbt": dbt_resource,
    },
)
