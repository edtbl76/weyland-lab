"""dbt (B1.5 Transform) → Dagster. The dbt project (`dbt/`) loads as Dagster assets via dagster-dbt: each model
materializes through **dbt-trino → Trino → Iceberg on the Nessie `main` ref**, with unified lineage/scheduling and
DataHub cataloging. The manifest is generated at IMAGE BUILD (`dbt parse` → `dbt/target/manifest.json`); @dbt_assets
reads it at import time. dbt only issues SQL to Trino — Trino owns the Nessie/MinIO writes (the meshed dagster pod
reaches `trino.data-mesh.svc` via the profile).

After `build`, the asset also runs `dbt docs generate` (fresh manifest + catalog against LIVE Trino — reliable HERE,
unlike the dbt-docs pod's boot-time generate) and PUBLISHES both to MinIO (`s3://warehouse/_dbt_artifacts/`) so the
DataHub dbt connector reads them via `s3://` — decoupled from the dbt-docs pod lifecycle. See
datahub-ingestion/dbt.recipe.yaml."""
import os
import subprocess
from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "dbt"   # /app/dbt (sibling of weyland_pipeline/)
dbt_manifest_path = DBT_PROJECT_DIR / "target" / "manifest.json"

dbt_resource = DbtCliResource(project_dir=str(DBT_PROJECT_DIR), profiles_dir=str(DBT_PROJECT_DIR))

# Publish target: the Iceberg warehouse bucket (already exists) under a DEDICATED `_dbt_artifacts/` prefix — NOT
# `dbt/`, which is where the Iceberg `dbt` schema writes its table data (parking JSON there mixed the artifacts in
# with the schema's parquet/metadata). The leading underscore keeps it out of the way of any schema named `dbt`.
# We write with the pod's ICEBERG_S3_* creds = the same nessie-secret S3 creds the DataHub executor reads the
# warehouse with → guaranteed same-bucket read access, no new secret. Overridable via env.
_ARTIFACT_BUCKET = os.environ.get("DBT_ARTIFACTS_BUCKET", "warehouse")
_ARTIFACT_PREFIX = os.environ.get("DBT_ARTIFACTS_PREFIX", "_dbt_artifacts")


def publish_dbt_artifacts(log=print):
    """Regenerate manifest.json + catalog.json (`dbt docs generate` against live Trino) and upload both to MinIO
    (`s3://<bucket>/<prefix>/`) for the DataHub dbt connector. Callable from the asset (weekly) or standalone
    (scripts/publish_dbt_artifacts.py). Raises on failure so the asset can log-and-continue."""
    from minio import Minio

    env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_PROJECT_DIR)}
    log("dbt docs generate — fresh manifest + catalog against live Trino…")
    subprocess.run(["dbt", "docs", "generate"], cwd=str(DBT_PROJECT_DIR), env=env, check=True)

    mc = Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["ICEBERG_S3_ACCESS_KEY"],
        secret_key=os.environ["ICEBERG_S3_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    for fn in ("manifest.json", "catalog.json"):
        src = DBT_PROJECT_DIR / "target" / fn
        mc.fput_object(_ARTIFACT_BUCKET, f"{_ARTIFACT_PREFIX}/{fn}", str(src), content_type="application/json")
        log(f"published dbt {fn} → s3://{_ARTIFACT_BUCKET}/{_ARTIFACT_PREFIX}/{fn}")


@dbt_assets(manifest=dbt_manifest_path)
def weyland_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # `build` = run models THEN run tests (unique/not-null + dbt-expectations ranges) — fail-fast on bad data.
    yield from dbt.cli(["build"], context=context).stream()
    # Publish fresh artifacts for the DataHub dbt connector. Best-effort: a docs/MinIO hiccup must NOT fail the
    # materialization — the marts + tests (the real product) already succeeded above.
    try:
        publish_dbt_artifacts(log=context.log.info)
    except Exception as e:  # noqa: BLE001
        context.log.warning(f"dbt docs publish skipped (build + tests succeeded): {e}")
