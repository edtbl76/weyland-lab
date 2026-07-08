"""dbt (B1.5 Transform) → Dagster. The dbt project (`dbt/`) loads as Dagster assets via dagster-dbt: each model
materializes through **dbt-trino → Trino → Iceberg on the Nessie `main` ref**, with unified lineage/scheduling and
DataHub cataloging. The manifest is generated at IMAGE BUILD (`dbt parse` → `dbt/target/manifest.json`); @dbt_assets
reads it at import time. dbt only issues SQL to Trino — Trino owns the Nessie/MinIO writes (the meshed dagster pod
reaches `trino.data-mesh.svc` via the profile)."""
from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "dbt"   # /app/dbt (sibling of weyland_pipeline/)
dbt_manifest_path = DBT_PROJECT_DIR / "target" / "manifest.json"

dbt_resource = DbtCliResource(project_dir=str(DBT_PROJECT_DIR), profiles_dir=str(DBT_PROJECT_DIR))


@dbt_assets(manifest=dbt_manifest_path)
def weyland_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    # `build` = run models THEN run tests (unique/not-null + dbt-expectations ranges) — fail-fast on bad data.
    yield from dbt.cli(["build"], context=context).stream()
