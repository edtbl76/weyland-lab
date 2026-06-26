"""B72 — CSV→Parquet transform (bronze→silver) for the MinIO `datasets` lake.

Reads every raw CSV under `s3://datasets/raw/<table>/*.csv`, converts it to Parquet (pyarrow,
schema inferred), and writes `s3://datasets/parquet/<table>/<name>.parquet`. The DataHub s3 source
then catalogs both zones (raw CSV + Parquet) with inferred schemas; the CSV→Parquet *lineage* edge
is wired in a follow-up once the s3 source confirms the real dataset URNs (same sequencing we used
for Iceberg). Reuses the pod's MINIO_* env (aidlc-kb-minio-secret) — those creds must be able to
read/write the `datasets` bucket.
"""
import io
import os

import pyarrow.csv as pacsv
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset
from minio import Minio


def _minio() -> Minio:
    return Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )


@asset(
    group_name="datasets",
    description="Convert raw CSVs (datasets/raw/<table>/) to Parquet (datasets/parquet/<table>/) on MinIO — bronze→silver.",
)
def csv_to_parquet(context) -> Output[dict]:
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    client = _minio()
    converted: dict = {}
    for obj in client.list_objects(bucket, prefix="raw/", recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        rel = obj.object_name[len("raw/"):]            # <table>/<file>.csv
        out_name = "parquet/" + rel[:-4] + ".parquet"  # parquet/<table>/<file>.parquet
        resp = client.get_object(bucket, obj.object_name)
        try:
            table = pacsv.read_csv(io.BytesIO(resp.read()))
        finally:
            resp.close()
            resp.release_conn()
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)
        client.put_object(
            bucket, out_name, buf, length=buf.getbuffer().nbytes,
            content_type="application/octet-stream",
        )
        converted[obj.object_name] = {"rows": table.num_rows, "cols": table.num_columns, "out": out_name}
        context.log.info(f"converted {obj.object_name} -> {out_name} ({table.num_rows} rows, {table.num_columns} cols)")

    if not converted:
        context.log.warning(f"no CSVs found under s3://{bucket}/raw/ — land data first (mc cp ...)")
    return Output(
        converted,
        metadata={
            "files_converted": MetadataValue.int(len(converted)),
            "total_rows": MetadataValue.int(sum(v["rows"] for v in converted.values())),
        },
    )
