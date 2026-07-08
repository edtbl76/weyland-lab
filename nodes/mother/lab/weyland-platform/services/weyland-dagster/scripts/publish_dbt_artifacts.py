"""Standalone: `dbt docs generate` + publish manifest.json/catalog.json to MinIO (s3://warehouse/dbt/) for the
DataHub dbt connector. Same code the weekly weyland_dbt_assets run calls — this just runs it on demand without a
full mart rebuild. Run in the dagster-user-code pod (has the dbt project + ICEBERG_S3_*/MINIO env + Trino access):

  kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/publish_dbt_artifacts.py
"""
import sys

sys.path.insert(0, "/app")
from weyland_pipeline.dbt_assets import publish_dbt_artifacts  # noqa: E402

if __name__ == "__main__":
    publish_dbt_artifacts()
