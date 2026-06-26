"""Publish selected Postgres tables to Iceberg (Nessie warehouse) as table data products.

Reads a table from Postgres and writes it to Iceberg via pyiceberg using `overwrite`
(idempotent full-snapshot — re-running replaces, never duplicates). Used by the Dagster
`iceberg_export` assets; also runnable standalone for testing:

    ICEBERG_S3_ACCESS_KEY=… ICEBERG_S3_SECRET_KEY=… python -m weyland_pipeline.iceberg_publish

Connects to Postgres via env (the dagster-user-code pod is meshed → reaches STRICT Postgres).
"""
import datetime
import os
from decimal import Decimal
from typing import Dict

import psycopg2
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog

from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetLineageTypeClass,
    UpstreamClass,
    UpstreamLineageClass,
)

# (iceberg namespace, iceberg table, postgres query, dagster asset that publishes it)
PRODUCTS = [
    ("catalog", "model_catalog", "SELECT * FROM model_catalog", "iceberg_model_catalog"),
    ("eval", "eval_scores", "SELECT * FROM eval_scores", "iceberg_eval_scores"),
]


def _catalog() -> RestCatalog:
    access = os.environ.get("ICEBERG_S3_ACCESS_KEY")
    secret = os.environ.get("ICEBERG_S3_SECRET_KEY")
    if not access or not secret:
        raise ValueError(
            "ICEBERG_S3_ACCESS_KEY / ICEBERG_S3_SECRET_KEY are unset. The dagster-user-code pod needs "
            "the `iceberg-s3-secret` env (k8s/dagster/user-code.yaml) — mirror nessie-secret's S3 creds "
            "into the weyland ns: kubectl -n weyland create secret generic iceberg-s3-secret "
            "--from-literal=access_key=... --from-literal=secret_key=..."
        )
    return RestCatalog(
        "nessie",
        **{
            "uri": os.environ.get(
                "NESSIE_ICEBERG_URI",
                "http://nessie.data-mesh.svc.cluster.local:19120/iceberg",
            ),
            "warehouse": os.environ.get("ICEBERG_WAREHOUSE", "warehouse"),
            "s3.endpoint": os.environ.get(
                "ICEBERG_S3_ENDPOINT", "http://minio.minio.svc.cluster.local:9000"
            ),
            "s3.access-key-id": access,
            "s3.secret-access-key": secret,
            "s3.region": "us-east-1",
            "s3.path-style-access": "true",
        },
    )


def _conv(v):
    if v is None or isinstance(v, (str, int, float, bool, datetime.datetime, datetime.date)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    return str(v)  # json/array/uuid/other → string, so pyiceberg gets a clean type


def _query_to_arrow(query: str) -> pa.Table:
    conn = psycopg2.connect(
        host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
        port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
        dbname=os.environ.get("WEYLAND_PG_DB", "weyland"),
        user=os.environ.get("WEYLAND_PG_USER", "weyland"),
        password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()
    arrays = {}
    for i, col in enumerate(cols):
        vals = [_conv(r[i]) for r in rows]
        # an all-NULL column is pyarrow null type, which Iceberg rejects → force string
        arrays[col] = pa.array(vals, type=pa.string()) if all(v is None for v in vals) else pa.array(vals)
    return pa.table(arrays)


def _emit_lineage(namespace: str, table: str, dagster_asset: str) -> None:
    """Cross-platform lineage: the iceberg dataset <- the dagster asset that publishes it.

    Connects the Dagster asset graph (platform=dagster, emitted by datahub_emit.py) to the
    iceberg-platform dataset the DataHub Iceberg source catalogs — completing the
    Postgres -> Dagster -> Iceberg chain in the catalog. Non-fatal: skipped if no DataHub
    token is present (the table write has already succeeded).
    """
    token = os.environ.get("DATAHUB_GMS_TOKEN")
    if not token:
        return
    server = os.environ.get(
        "DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080"
    )
    iceberg_urn = make_dataset_urn("iceberg", f"{namespace}.{table}", "PROD")
    dagster_urn = make_dataset_urn("dagster", dagster_asset, "PROD")
    DatahubRestEmitter(gms_server=server, token=token).emit(
        MetadataChangeProposalWrapper(
            entityUrn=iceberg_urn,
            aspect=UpstreamLineageClass(
                upstreams=[UpstreamClass(dataset=dagster_urn, type=DatasetLineageTypeClass.TRANSFORMED)]
            ),
        )
    )


def publish_table(namespace: str, table: str, query: str, dagster_asset: str) -> int:
    arrow = _query_to_arrow(query)
    catalog = _catalog()
    try:
        catalog.create_namespace(namespace)
    except Exception:
        pass  # already exists
    iceberg_table = catalog.create_table_if_not_exists(f"{namespace}.{table}", schema=arrow.schema)
    iceberg_table.overwrite(arrow)
    _emit_lineage(namespace, table, dagster_asset)
    return arrow.num_rows


def publish_all() -> Dict[str, int]:
    return {f"{ns}.{tbl}": publish_table(ns, tbl, q, asset) for ns, tbl, q, asset in PRODUCTS}


if __name__ == "__main__":
    print(publish_all())
