"""B72 step 2 — fan-out transform (silver + gold).

For each raw CSV under datasets/raw/<table>/, load it ONCE into a pyarrow Table, then write:
  - parquet/<table>/  (pyarrow)        — batch columnar
  - arrow/<table>/    (pyarrow feather) — IPC / zero-copy
  - avro/<table>/     (fastavro)        — row-oriented / streaming
  - lance/<table>     (pylance → S3)    — ML / vector
  - Iceberg datasets.<table> (pyiceberg → Nessie) — ACID gold table

Each writer is wrapped independently: a failing format reports its error and the rest still land.
Depends on datasets_land (lineage) and is what the datasets_raw S3 sensor triggers.
"""
import io
import os

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.feather as feather
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


def _put(client: Minio, bucket: str, key: str, data: bytes) -> None:
    client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type="application/octet-stream")


def _write_parquet(client, bucket, table, name, t):
    buf = io.BytesIO()
    pq.write_table(t, buf)
    _put(client, bucket, f"parquet/{table}/{name}.parquet", buf.getvalue())


def _write_arrow(client, bucket, table, name, t):
    sink = pa.BufferOutputStream()
    feather.write_feather(t, sink)
    _put(client, bucket, f"arrow/{table}/{name}.arrow", sink.getvalue().to_pybytes())


_AVRO_TYPE = {
    "int64": "long", "int32": "int", "double": "double", "float": "float",
    "bool": "boolean", "string": "string", "large_string": "string",
}


def _write_avro(client, bucket, table, name, t):
    import fastavro

    fields = [
        {"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
        for f in t.schema
    ]
    schema = fastavro.parse_schema({"type": "record", "name": f"{table}_record", "fields": fields})
    # any column whose arrow type we mapped to avro string must be stringified to match the schema
    str_cols = {f.name for f in t.schema if _AVRO_TYPE.get(str(f.type), "string") == "string"
                and str(f.type) not in ("string", "large_string")}
    records = t.to_pylist()
    if str_cols:
        for r in records:
            for c in str_cols:
                if r.get(c) is not None:
                    r[c] = str(r[c])
    buf = io.BytesIO()
    fastavro.writer(buf, schema, records)
    _put(client, bucket, f"avro/{table}/{name}.avro", buf.getvalue())


def _write_lance(table, t):
    import lance

    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    uri = f"s3://{bucket}/lance/{table}"
    storage_options = {
        "access_key_id": os.environ["MINIO_ACCESS_KEY"],
        "secret_access_key": os.environ["MINIO_SECRET_KEY"],
        "endpoint": os.environ.get("MINIO_ENDPOINT_URL", "http://minio.minio.svc.cluster.local:9000"),
        "allow_http": "true",
        "region": "us-east-1",
    }
    lance.write_dataset(t, uri, mode="overwrite", storage_options=storage_options)


def _hydrate_iceberg(table, t):
    from weyland_pipeline.iceberg_publish import _catalog

    cat = _catalog()
    cat.create_namespace_if_not_exists("datasets")
    ice = cat.create_table_if_not_exists(f"datasets.{table}", schema=t.schema)
    ice.overwrite(t)


@asset(
    group_name="datasets",
    deps=["datasets_land"],
    description="Fan-out transform: raw CSV → Parquet/Arrow/Avro/Lance (silver) + Iceberg (gold). Per-format resilient.",
)
def datasets_transform(context) -> Output[dict]:
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    client = _minio()
    results: dict = {}
    for obj in client.list_objects(bucket, prefix="raw/", recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        rel = obj.object_name[len("raw/"):]      # <table>/<file>.csv
        table = rel.split("/")[0]
        name = os.path.basename(rel)[:-4]
        resp = client.get_object(bucket, obj.object_name)
        try:
            t = pacsv.read_csv(io.BytesIO(resp.read()))
        finally:
            resp.close()
            resp.release_conn()

        status: dict = {"rows": t.num_rows, "cols": t.num_columns}
        writers = (
            ("parquet", lambda: _write_parquet(client, bucket, table, name, t)),
            ("arrow", lambda: _write_arrow(client, bucket, table, name, t)),
            ("avro", lambda: _write_avro(client, bucket, table, name, t)),
            ("lance", lambda: _write_lance(table, t)),
            ("iceberg", lambda: _hydrate_iceberg(table, t)),
        )
        for fmt, fn in writers:
            try:
                fn()
                status[fmt] = "ok"
            except Exception as e:  # noqa: BLE001 — one bad format must not block the rest
                status[fmt] = f"ERROR {type(e).__name__}: {e}"
                context.log.error(f"{table}/{name} [{fmt}] failed: {e}")
        results[f"{table}/{name}"] = status
        context.log.info(f"{table}/{name}: {status}")

    if not results:
        context.log.warning("no CSVs under datasets/raw/ — run datasets_land first")
    return Output(results, metadata={"files": MetadataValue.int(len(results)), "detail": MetadataValue.json(results)})
