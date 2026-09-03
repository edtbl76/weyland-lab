import os
from dagster import Definitions, ScheduleDefinition, job, op, DefaultScheduleStatus, in_process_executor
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
    registrations_reconcile_job,
    registrations_schedule,
)
from weyland_pipeline.sensors import datasets_music_raw_sensor
from weyland_pipeline.lancedb_sync import weyland_lancedb_sync_job, lancedb_sync_sensor

# B49(b) Phase 2 — start app-level tracing → Tempo (opt-in via OTEL_EXPORTER_OTLP_ENDPOINT). Called at code-location
# import so it also initializes INSIDE each forked op subprocess (the multiprocess executor re-imports this module).
from weyland_pipeline._otel import init_otel
init_otel()

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
def emit_dbt_openlineage_op(context):
    # dbt RUN-HISTORY (OpenLineage → DataHub DataFlow/DataJob/DataProcessInstance). Reads the BUILD run_results the
    # dbt asset preserved to MinIO (run_results_build.json); no-op if a build hasn't published one yet.
    from weyland_pipeline.datahub_emit import emit_dbt_openlineage
    _safe_emit(context, "dbt run-history (OpenLineage)", lambda: emit_dbt_openlineage(dry_run=False))


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
def emit_applications_op(context):
    from weyland_pipeline.datahub_emit import emit_applications
    _safe_emit(context, "Applications (create + attach assets to owning app)", emit_applications)


@op
def emit_port_components_op(context):
    from weyland_pipeline.datahub_emit import emit_port_components
    _safe_emit(context, "Port components (registry → Port, closes B137 registry↔Port drift)",
               emit_port_components)


@op
def emit_eval_assertions_op(context):
    from weyland_pipeline.datahub_emit import emit_eval_assertions
    _safe_emit(context, "Eval leaderboard contract (assertions)", emit_eval_assertions)


@op
def emit_asset_check_assertions_op(context):
    from weyland_pipeline.datahub_emit import emit_asset_check_assertions
    _safe_emit(context, "Asset-check GATE → per-silver-table Assertions (B77)",
               lambda: emit_asset_check_assertions(context.instance))


@op
def emit_data_contracts_op(context):
    from weyland_pipeline.datahub_emit import emit_data_contracts
    _safe_emit(context, "Data Contracts (per data-mesh dataset, all 3 assertion sources — B80)",
               emit_data_contracts)


@op
def emit_siblings_op(context):
    from weyland_pipeline.datahub_emit import emit_siblings
    _safe_emit(context, "Siblings (merge trino/dbt/iceberg twins → one entity so governance is visible — B80)",
               emit_siblings)


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
    DataHub (assertions/profiles; contracts now emit mesh-wide from datahub_catalog_emit_job — B80). Soda exit codes: 0 = all pass, 1 = warnings, 2 = check failures,
    3 = execution error. Fail the op if ANY scan is >= 2 so a broken contract surfaces as a red Dagster run."""
    import json
    import subprocess
    from dagster import Failure
    from weyland_pipeline.datahub_emit import (
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
        ("weyland_music", "/tmp/soda_music.json", ["/app/soda/checks/music_silver.yml", _bl]),
        ("weyland_health", "/tmp/soda_gold.json", ["/app/soda/checks/health_gold.yml", _bl]),
        # B113 Phase 1 — finance silver/gold (fred_macro, fred_series_meta); baseline.yml fans row_count>0 across
        # every datasets_finance table too. mart_macro_indicators is covered by the `weyland` marts scan above.
        ("weyland_finance", "/tmp/soda_finance.json", ["/app/soda/checks/finance.yml", _bl]),
    ]
    worst = 0
    marts_bad = False
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
        if ds == "weyland" and result.returncode >= 2:  # marts = strict data contract; silver is advisory (below)
            marts_bad = True
        # Emit BEFORE the fail check so failing checks still surface in the catalog. Non-fatal per scan.
        try:
            with open(results_file) as f:
                scan_results = json.load(f)
            context.log.info(f"DataHub [{ds}]: {emit_soda_assertions(scan_results)} assertions, "
                             f"{emit_soda_profiles(scan_results)} profiles (Stats)")
        except Exception as e:
            context.log.warning(f"DataHub quality emit skipped for {ds} (non-fatal): {e}")
    # Marts (data source `weyland`) violating their contract = a real failure → raise. SILVER source-data findings
    # (dirty ages, 0-duration tracks in downloaded datasets we don't control) are ADVISORY: already emitted to
    # DataHub as failing assertions above, so they show red on the Quality tabs without failing the pipeline
    # (B77 Soda-to-silver posture, 2026-08-06).
    if marts_bad:
        raise Failure(description="Soda scan failed — a MART violated its data contract.")
    if worst >= 2:
        context.log.warning(f"Soda SILVER check(s) failed (exit {worst}) — advisory only; findings are on the "
                            f"datasets' DataHub Quality tabs, not failing the job.")
    return worst


@job
def soda_quality_job():
    soda_scan_op()


# in_process_executor: 27 dependency-free emit ops otherwise fan out under the default multiprocess executor,
# each op-subprocess re-importing the full ~1.1 GB definitions → N-concurrent × 1.1 GB OOM'd the 12 Gi pod even
# though every emit function is individually cheap (~1.24 GB cumulative). One process, one import, ops run
# sequentially → ~1.3 GB peak, and faster (no per-op subprocess spawn + re-import).
@job(executor_def=in_process_executor, tags={"dagster/max_runtime": 1800})
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
    emit_dbt_openlineage_op()
    emit_feast_op()
    emit_lightdash_op()
    emit_domains_op()
    emit_data_products_op()
    emit_applications_op()
    emit_port_components_op()   # B78 follow-up — reconcile registry → Port components (both surfaces, one file)
    emit_eval_assertions_op()
    emit_asset_check_assertions_op()
    emit_data_contracts_op()   # B80 — AFTER asset-check assertions so the per-dataset query picks them up
    emit_siblings_op()         # B80 — merge the platform twins so assertions/contracts show on any of them
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


@job(executor_def=in_process_executor)
def datahub_asset_check_assertions_job():
    """B77 verify / fast-path — emit ONLY the asset-check GATE assertions (skips the full 28-op catalog run)."""
    emit_asset_check_assertions_op()


@op
def ge_validate_op(context):
    """B77 part (b) — on-demand Great Expectations. Shell out to the isolated /opt/ge-venv (GE's pins clash with the
    main env, same as Soda) to auto-profile + validate the showcase tables, then surface results via the MAIN-env
    emit_ge_assertions (acryl dropped the native GE action). Advisory — GE findings never fail the job."""
    import subprocess
    from weyland_pipeline.datahub_emit import emit_ge_assertions
    cmd = ["/opt/ge-venv/bin/python", "/app/ge/ge_validate.py"]
    context.log.info("Running: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout:
        context.log.info(r.stdout)
    if r.stderr:
        context.log.warning(r.stderr)
    _safe_emit(context, "Great Expectations → DataHub Assertions (B77 part b)", emit_ge_assertions)
    if r.returncode != 0:
        context.log.warning(f"GE runner exit {r.returncode} — advisory (findings in DataHub + Data Docs), not failing the job.")
    return r.returncode


@job(executor_def=in_process_executor, tags={"dagster/max_runtime": 1800})
def ge_validate_job():
    """B77 part (b) — on-demand Great Expectations: auto-profile + validate the showcase tables → DataHub Assertions + Data Docs (ge-docs.weyland.lab)."""
    ge_validate_op()


@op
def feast_materialize_op(context):
    """B140 — push the Feast OFFLINE store (Postgres `feast` DB) into the ONLINE store (Valkey).

    WHY THIS EXISTS, and why it does NOT use `materialize-incremental`:

    Found 2026-08-24 while writing a smoke test for feast-server. The online store was EMPTY — Valkey
    held 228 keys, all `bull:*` (Langfuse's queue) and zero Feast keys — while feast-server was
    Argo-healthy, REST-answering and green on its `/health` probe. Every entity key returned `null`,
    including fabricated ones like `nonexistent-key-xyz`.

    The cause is a self-perpetuating trap. `feast_metadata` already held a materialization watermark of
    **2026-07-08** (the B1.8 setup run), and `materialize-incremental` only scans FORWARD from that
    watermark. Every event timestamp in the data predates it — `track_audio_features` is stamped
    2020-01-01, `state_health_risk` spans 2011→2024 — so the incremental window is permanently empty.
    Each run therefore "succeeds", writes nothing, prints no progress bar, emits no error, and leaves
    the watermark such that the NEXT run is equally empty. Forever.

    So: an EXPLICIT window from before the earliest event time. `FEAST_MATERIALIZE_START` overrides it
    if the sources ever gain older rows.

    AND THE OP VERIFIES ITS OWN WORK. `feast materialize` exits 0 whether it wrote 89,741 rows or
    nothing at all, so trusting the exit code here would rebuild the exact bug this op fixes. It
    samples a REAL entity key out of the offline table (never a hardcoded one — a hardcoded key can
    silently stop existing) and asserts the online store returns a NON-NULL value for it.

    Note `statuses: ["PRESENT"]` is NOT evidence: Feast returns PRESENT with `values: [null]` for keys
    that were never materialized. PRESENT describes the response row, not a found feature. The
    assertion must be on the value.
    """
    import os
    import subprocess
    from datetime import datetime, timezone

    from dagster import Failure

    repo = "/app/feast_repo"
    start = os.environ.get("FEAST_MATERIALIZE_START", "2010-01-01T00:00:00")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    cmd = ["feast", "materialize", start, end]
    context.log.info("Running: " + " ".join(cmd) + f"  (cwd={repo})")
    result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if result.stdout:
        context.log.info(result.stdout)
    if result.returncode != 0:
        raise Failure(
            f"feast materialize exited {result.returncode}. stderr: {(result.stderr or '')[-2000:]}"
        )

    # --- verification: did anything actually land? -------------------------------------------
    import psycopg2
    from feast import FeatureStore

    dsn = (
        f"host=weyland-postgres.weyland.svc.cluster.local port=5432 dbname=feast "
        f"user=weyland password={os.environ.get('WEYLAND_PG_PASSWORD', '')} sslmode=disable"
    )
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT state FROM state_health_risk ORDER BY event_timestamp DESC LIMIT 1")
        row = cur.fetchone()
    if not row or not row[0]:
        raise Failure("offline table state_health_risk is empty — nothing could be materialized")
    sample_key = row[0]

    store = FeatureStore(repo_path=repo)
    feats = store.get_online_features(
        features=["state_health_risk:depression_pct"],
        entity_rows=[{"state": sample_key}],
    ).to_dict()
    values = feats.get("depression_pct") or []
    if not values or values[0] is None:
        raise Failure(
            f"feast materialize reported success but the online store serves NOTHING for a real "
            f"entity key ({sample_key!r}). This is the silent no-op the op exists to prevent — check "
            f"the materialization window against the sources' event_timestamp range."
        )

    context.log.info(
        f"verified: online store serves state={sample_key!r} depression_pct={values[0]}"
    )


@job(executor_def=in_process_executor, tags={"dagster/max_runtime": 1800})
def feast_materialize_job():
    """B140 — offline (Postgres) → online (Valkey) for the Feast feature views, with self-verification."""
    feast_materialize_op()


feast_materialize_schedule = ScheduleDefinition(
    job=feast_materialize_job,
    # 00:05 daily — inside the 00:00–06:00 off-hours window (schedules.md Design Rule #5) and clear of
    # 00:20 timeseries. Light: the full 89,741-row materialize takes seconds. Daily rather than weekly
    # because it is cheap and, if the offline sources are ever reloaded, a stale online store is
    # exactly the invisible failure this whole item is about.
    cron_schedule="5 0 * * *",
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.RUNNING,
)


datahub_catalog_emit_schedule = ScheduleDefinition(
    job=datahub_catalog_emit_job,
    cron_schedule="35 0 * * *",  # daily 00:35 — OVERNIGHT-ONLY (no mid-day auto-runs; single-node RAM guard, 2026-08-07) — per docs/schedules.md
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

# B69 Wave 4 — un-freeze the eval harness. The B4 leaderboard was manual-only, so it silently stopped being
# refreshed and the "which model is defensible?" answer aged out. Two jobs, run in order: the matrix first
# (question-gen + RAG × models), then the 3-judge scoring pass over its results.
#
# WEEKLY, on SATURDAY — the one genuinely quiet day: Sunday already carries dbt (06:00), sonar (08:00),
# scan-suite (09:00) and the image prune (11:00), and every day carries the 02:17 ingestion. Two hours between
# the two jobs so the matrix finishes before judging starts (they're chained by data, not by a sensor).
#
# STOPPED by default, exactly like soda_quality_schedule above: Ollama MOVED TO ROGUEONE in B79, so the eval
# path hasn't been exercised since. Enable both in the Dagster UI only AFTER a manual run comes back green —
# scheduling an already-broken heavy job just manufactures weekly noise.
weyland_eval_schedule = ScheduleDefinition(
    job=weyland_eval_job,
    cron_schedule="0 3 * * 6",  # Sat 03:00 — question-gen + run-matrix (HEAVY: RAG × 6 models)
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.STOPPED,
)

weyland_eval_score_schedule = ScheduleDefinition(
    job=weyland_eval_score_job,
    cron_schedule="0 5 * * 6",  # Sat 05:00 — 3-judge panel scores the matrix written at 03:00
    execution_timezone="America/New_York",
    default_status=DefaultScheduleStatus.STOPPED,
)

defs = Definitions(
    assets=[*all_assets, weyland_dbt_assets],
    asset_checks=all_asset_checks,
    jobs=[feast_materialize_job, weyland_ingestion_job, weyland_eval_job, weyland_eval_score_job, weyland_catalog_job, weyland_aidlc_kb_job, weyland_ai_session_job, datahub_catalog_emit_job, datahub_asset_check_assertions_job, ge_validate_job, weyland_datasets_music_transform_job, weyland_datasets_music_land_job, weyland_datasets_health_land_job, weyland_datasets_health_transform_job, weyland_datasets_health_hydrate_job, weyland_datasets_music_hydrate_job, weyland_timeseries_job, weyland_lancedb_sync_job, weyland_dbt_job, soda_quality_job, registrations_reconcile_job],
    schedules=[feast_materialize_schedule, weyland_ingestion_schedule, weyland_catalog_schedule, weyland_ai_session_schedule, datahub_catalog_emit_schedule, weyland_timeseries_schedule, weyland_datasets_music_land_schedule, weyland_datasets_health_land_schedule, weyland_dbt_schedule, soda_quality_schedule, weyland_eval_schedule, weyland_eval_score_schedule, registrations_schedule],
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
