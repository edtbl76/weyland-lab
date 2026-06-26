"""B72 — fan-out transform (silver + gold), BROKERED as one asset PER format.

Rather than one monolith (where a single bad source read sinks every format), each output format is
its own Dagster asset — datasets_parquet / _arrow / _avro / _lance / _iceberg — all depending on
datasets_land. Dagster's multiprocess executor runs each in its OWN child process, so a failure —
even a NATIVE crash (e.g. Lance's Rust S3 writer) — is isolated to that format's asset; the others
still land. The asset graph IS the broker.

Source CSVs are read once per asset with newlines_in_values=True (FMA/Spotify cells carry embedded
newlines), and an unreadable file is skipped, not fatal. (Each asset re-reads raw/ — cheap on the LAN
and the price of full process isolation; passing big Arrow tables between assets would lose it.)
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


def _put(client, bucket, key, data: bytes):
    client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type="application/octet-stream")


def _catalog_file(platform, table, location, schema, producer):
    """Best-effort custom-emit to DataHub — Arrow/Lance have NO native connector, so they're catalogued
    here. A DataHub hiccup must NOT fail the file write that already succeeded."""
    try:
        from weyland_pipeline.datahub_emit import emit_file_dataset

        emit_file_dataset(platform, table, location, schema, producer)
    except Exception as e:  # noqa: BLE001 — catalog is best-effort; the bytes are already written
        print(f"[datasets] DataHub emit {platform}/{table} failed (file written OK): {e}")


_PARSE = pacsv.ParseOptions(newlines_in_values=True)  # FMA/Spotify cells contain embedded newlines


def _iter_raw_tables(client, bucket, log):
    """Yield (table, name, arrow_table) for each raw CSV; an unreadable file is skipped, not fatal."""
    for obj in client.list_objects(bucket, prefix="raw/", recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        rel = obj.object_name[len("raw/"):]      # <table>/<file>.csv
        table = rel.split("/")[0]
        name = os.path.basename(rel)[:-4]
        resp = client.get_object(bucket, obj.object_name)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        try:
            t = pacsv.read_csv(io.BytesIO(data), parse_options=_PARSE)
        except Exception as e:  # noqa: BLE001 — one unreadable source must not sink the format
            log.error(f"skip raw/{rel}: CSV parse failed: {e}")
            continue
        yield table, name, t


# --- format writers (uniform signature so the broker calls them interchangeably) ---
def _write_parquet(client, bucket, table, name, t):
    buf = io.BytesIO()
    pq.write_table(t, buf)
    _put(client, bucket, f"parquet/{table}/{name}.parquet", buf.getvalue())
    _catalog_file("parquet", table, f"s3://{bucket}/parquet/{table}/", t.schema, "datasets_parquet")
    # also catalog the BRONZE raw CSV here (it has the same schema, read once) — the DataHub s3 source
    # that would have done this is unusable (its PySpark crashes on the executor's JDK), so we emit it.
    _catalog_file("s3", table, f"s3://{bucket}/raw/{table}/", t.schema, "datasets_land")


def _write_arrow(client, bucket, table, name, t):
    sink = pa.BufferOutputStream()
    feather.write_feather(t, sink)
    _put(client, bucket, f"arrow/{table}/{name}.arrow", sink.getvalue().to_pybytes())
    _catalog_file("arrow", table, f"s3://{bucket}/arrow/{table}/", t.schema, "datasets_arrow")


_AVRO_TYPE = {"int64": "long", "int32": "int", "double": "double", "float": "float",
              "bool": "boolean", "string": "string", "large_string": "string"}


def _write_avro(client, bucket, table, name, t):
    import fastavro

    fields = [{"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
              for f in t.schema]
    schema = fastavro.parse_schema({"type": "record", "name": f"{table}_record", "fields": fields})
    str_cols = {f.name for f in t.schema
                if _AVRO_TYPE.get(str(f.type), "string") == "string" and str(f.type) not in ("string", "large_string")}
    records = t.to_pylist()
    if str_cols:
        for r in records:
            for c in str_cols:
                if r.get(c) is not None:
                    r[c] = str(r[c])
    buf = io.BytesIO()
    fastavro.writer(buf, schema, records)
    _put(client, bucket, f"avro/{table}/{name}.avro", buf.getvalue())
    _catalog_file("avro", table, f"s3://{bucket}/avro/{table}/", t.schema, "datasets_avro")


def _write_lance(client, bucket, table, name, t):
    import lance

    uri = f"s3://{bucket}/lance/{table}"
    storage_options = {
        "access_key_id": os.environ["MINIO_ACCESS_KEY"],
        "secret_access_key": os.environ["MINIO_SECRET_KEY"],
        "endpoint": os.environ.get("MINIO_ENDPOINT_URL", "http://minio.minio.svc.cluster.local:9000"),
        "allow_http": "true",
        "region": "us-east-1",
    }
    lance.write_dataset(t, uri, mode="overwrite", storage_options=storage_options)
    _catalog_file("lance", table, uri, t.schema, "datasets_lance")


def _hydrate_iceberg(client, bucket, table, name, t):
    from weyland_pipeline.iceberg_publish import _catalog

    cat = _catalog()
    cat.create_namespace_if_not_exists("datasets")
    ice = cat.create_table_if_not_exists(f"datasets.{table}", schema=t.schema)
    ice.overwrite(t)


def _run_format(context, write_one) -> Output:
    client = _minio()
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    out: dict = {}
    for table, name, t in _iter_raw_tables(client, bucket, context.log):
        key = f"{table}/{name}"
        try:
            write_one(client, bucket, table, name, t)
            out[key] = f"ok ({t.num_rows}r x {t.num_columns}c)"
        except Exception as e:  # noqa: BLE001 — per-table resilience within a format
            out[key] = f"ERROR {type(e).__name__}: {e}"
            context.log.error(f"{key}: {e}")
    if not out:
        context.log.warning("no raw CSVs under datasets/raw/ — run datasets_land first")
    return Output(out, metadata={
        "ok": MetadataValue.int(sum(1 for v in out.values() if v.startswith("ok"))),
        "detail": MetadataValue.json(out),
    })


_COMMON = dict(group_name="datasets", deps=["datasets_land"])


@asset(**_COMMON, description="Silver — Parquet (batch columnar) for each raw table.")
def datasets_parquet(context) -> Output[dict]:
    return _run_format(context, _write_parquet)


@asset(**_COMMON, description="Silver — Arrow/Feather (IPC) for each raw table.")
def datasets_arrow(context) -> Output[dict]:
    return _run_format(context, _write_arrow)


@asset(**_COMMON, description="Silver — Avro (row-oriented / streaming) for each raw table.")
def datasets_avro(context) -> Output[dict]:
    return _run_format(context, _write_avro)


@asset(**_COMMON, description="Silver — Lance (ML/vector) for each raw table. Native Rust S3 writer — isolated.")
def datasets_lance(context) -> Output[dict]:
    return _run_format(context, _write_lance)


@asset(**_COMMON, description="Gold — Iceberg table (Nessie) for each raw table.")
def datasets_iceberg(context) -> Output[dict]:
    return _run_format(context, _hydrate_iceberg)
