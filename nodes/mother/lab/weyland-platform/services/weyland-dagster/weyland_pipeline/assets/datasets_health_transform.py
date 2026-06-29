"""B72 — health dataset fan-out transform (silver + gold), BROKERED as one asset PER format.

Mirror of datasets_music_transform.py for the HEALTH lakeFS repo, with two health-specific differences:

1. Multi-format reader. Health sources don't all land as CSV — NHANES is SAS `.XPT`, WHO GHO is OData
   `.json` ({"value":[...]}), Open Food Facts is a `.csv.gz`. `_read_to_table` dispatches on extension
   (case-insensitive) and returns ONE Arrow table per source; an unreadable/unknown file is skipped, not
   fatal. No flattening — Arrow/Parquet/Avro carry nested JSON natively; XPT is already rectangular.

2. Per-format allowlists keyed by raw/ folder (source of truth: docs/data-domain-storage-grid.csv).
   Parquet/Arrow/Avro/Iceberg are "Y" for every health dataset; Lance is selective.

Each output format is its own Dagster asset (multiprocess executor → own child process), so a failure —
even a native Lance Rust-S3 crash — is isolated to that format. The asset graph IS the broker.
"""
import gzip
import io
import json
import os
import re

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.feather as feather
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset
from minio import Minio


# Write THROUGH the lakeFS S3 gateway (versioned) to the HEALTH repo, not MinIO directly.
_REPO = "health"
_BRANCH = os.environ.get("LAKEFS_BRANCH", "main")


def _minio() -> Minio:
    ep = os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")
    return Minio(
        ep.replace("https://", "").replace("http://", ""),
        access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
        secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        secure=ep.startswith("https://"),
    )


def _k(key: str) -> str:
    return f"{_BRANCH}/{key}"


def _put(client, bucket, key, data: bytes):
    client.put_object(bucket, _k(key), io.BytesIO(data), length=len(data), content_type="application/octet-stream")


def _catalog_file(platform, table, location, schema, producer):
    """Best-effort custom-emit to DataHub — Arrow/Lance have NO native connector. A DataHub hiccup must
    NOT fail the file write that already succeeded."""
    try:
        from weyland_pipeline.datahub_emit import emit_file_dataset

        emit_file_dataset(platform, table, location, schema, producer)
    except Exception as e:  # noqa: BLE001 — catalog is best-effort; the bytes are already written
        print(f"[datasets_health] DataHub emit {platform}/{table} failed (file written OK): {e}")


_PARSE = pacsv.ParseOptions(newlines_in_values=True)
_EXT_RE = re.compile(r"\.(csv\.gz|csv|xpt|json)$", re.IGNORECASE)


def _read_to_table(rel, data, log):
    """Read one raw object into an Arrow table, dispatching on extension. Returns None to skip
    (unknown extension or unreadable) — one bad source must not sink the whole format."""
    low = rel.lower()
    try:
        if low.endswith(".csv.gz"):
            return pacsv.read_csv(io.BytesIO(gzip.decompress(data)), parse_options=_PARSE)
        if low.endswith(".csv"):
            return pacsv.read_csv(io.BytesIO(data), parse_options=_PARSE)
        if low.endswith(".xpt"):
            import pandas as pd  # SAS transport — already rectangular, just needs a reader

            df = pd.read_sas(io.BytesIO(data), format="xport")
            # NHANES XPT string columns come back as bytes — decode to str so Arrow types them as string.
            for c in df.select_dtypes(include=["object"]).columns:
                df[c] = df[c].map(lambda v: v.decode("utf-8", "replace").strip() if isinstance(v, (bytes, bytearray)) else v)
            return pa.Table.from_pandas(df, preserve_index=False)
        if low.endswith(".json"):
            obj = json.loads(data)
            # WHO GHO OData: records live under "value". Fall back to the first list-of-records value,
            # or a bare top-level list.
            if isinstance(obj, dict):
                records = obj.get("value")
                if records is None:
                    records = next((v for v in obj.values() if isinstance(v, list)), None)
            else:
                records = obj
            if not records:
                log.warning(f"{rel}: JSON has no record list — skipping")
                return None
            return pa.Table.from_pylist(records)
    except Exception as e:  # noqa: BLE001 — one unreadable source must not sink the format
        log.error(f"skip raw/{rel}: read failed ({type(e).__name__}: {e})")
        return None
    log.warning(f"skip raw/{rel}: unsupported extension")
    return None


def _iter_raw_tables(client, bucket, log):
    """Yield (table, name, arrow_table) for each readable raw object. table = top-level folder;
    name = path within the table (slashes → underscores, extension stripped) so NHANES' nested
    cycle folders (2017-2020/DEMO_J.XPT) stay distinct."""
    raw_prefix = _k("raw/")
    for obj in client.list_objects(bucket, prefix=raw_prefix, recursive=True):
        rel = obj.object_name[len(raw_prefix):]      # <table>/<...>/<file>.<ext>
        table = rel.split("/")[0]
        resp = client.get_object(bucket, obj.object_name)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        t = _read_to_table(rel, data, log)
        if t is None:
            continue
        inner = rel[len(table) + 1:]
        name = _EXT_RE.sub("", inner).replace("/", "_")
        yield table, name, t


# --- format writers (uniform signature so the broker calls them interchangeably) ---
def _write_parquet(client, bucket, table, name, t):
    buf = io.BytesIO()
    pq.write_table(t, buf)
    _put(client, bucket, f"parquet/{table}/{name}.parquet", buf.getvalue())
    _catalog_file("parquet", table, f"lakefs://{bucket}/{_BRANCH}/parquet/{table}/", t.schema, "datasets_health_parquet")
    _catalog_file("s3", table, f"lakefs://{bucket}/{_BRANCH}/raw/{table}/", t.schema, "datasets_health_land")


def _write_arrow(client, bucket, table, name, t):
    sink = pa.BufferOutputStream()
    feather.write_feather(t, sink)
    _put(client, bucket, f"arrow/{table}/{name}.arrow", sink.getvalue().to_pybytes())
    _catalog_file("arrow", table, f"lakefs://{bucket}/{_BRANCH}/arrow/{table}/", t.schema, "datasets_health_arrow")


_AVRO_TYPE = {"int64": "long", "int32": "int", "double": "double", "float": "float",
              "bool": "boolean", "string": "string", "large_string": "string"}


def _write_avro(client, bucket, table, name, t):
    import fastavro

    fields = [{"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
              for f in t.schema]
    schema = fastavro.parse_schema({"type": "record", "name": f"{table}_{name}_record".replace("-", "_"), "fields": fields})
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
    _catalog_file("avro", table, f"lakefs://{bucket}/{_BRANCH}/avro/{table}/", t.schema, "datasets_health_avro")


def _write_lance(client, bucket, table, name, t):
    import lance

    uri = f"s3://{bucket}/{_BRANCH}/lance/{table}/{name}"
    storage_options = {
        "access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
        "secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        "endpoint": os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000"),
        "allow_http": "true",
        "region": "us-east-1",
    }
    lance.write_dataset(t, uri, mode="overwrite", storage_options=storage_options)
    _catalog_file("lance", table, f"lakefs://{bucket}/{_BRANCH}/lance/{table}/", t.schema, "datasets_health_lance")


def _hydrate_iceberg(client, bucket, table, name, t):
    from weyland_pipeline.iceberg_publish import _catalog

    cat = _catalog()
    # Flat prefixed namespace (datasets_health) — Nessie nested namespaces are invisible to Trino
    # catalog.type=nessie (see datasets_music_transform.py for the full rationale).
    cat.create_namespace_if_not_exists("datasets_health")
    ice = cat.create_table_if_not_exists(f"datasets_health.{table}", schema=t.schema)
    with ice.update_schema() as update:
        update.union_by_name(t.schema)
    ice = cat.load_table(f"datasets_health.{table}")
    ice.overwrite(t)


# --- per-format allowlists (source of truth: docs/data-domain-storage-grid.csv) ---
_HEALTH_ALL = {
    "nhanes", "big_five", "who_gho", "cdc_physical_activity",
    "brfss", "nhis", "usda_fooddata", "open_food_facts",
}
_PARQUET_ALLOW = _HEALTH_ALL
_ARROW_ALLOW = _HEALTH_ALL
_AVRO_ALLOW = _HEALTH_ALL
_ICEBERG_ALLOW = _HEALTH_ALL
_LANCE_ALLOW = {"big_five", "usda_fooddata", "open_food_facts"}


def _run_format(context, write_one, allow) -> Output:
    client = _minio()
    bucket = _REPO
    out: dict = {}
    for table, name, t in _iter_raw_tables(client, bucket, context.log):
        key = f"{table}/{name}"
        if table not in allow:
            out[key] = "skipped (not in allowlist)"
            continue
        try:
            write_one(client, bucket, table, name, t)
            out[key] = f"ok ({t.num_rows}r x {t.num_columns}c)"
        except Exception as e:  # noqa: BLE001 — per-table resilience within a format
            out[key] = f"ERROR {type(e).__name__}: {e}"
            context.log.error(f"{key}: {e}")
    if not out:
        context.log.warning("no readable raw under health/raw/ — run datasets_health_*_land first")
    return Output(out, metadata={
        "ok": MetadataValue.int(sum(1 for v in out.values() if v.startswith("ok"))),
        "skipped": MetadataValue.int(sum(1 for v in out.values() if v.startswith("skipped"))),
        "detail": MetadataValue.json(out),
    })


_COMMON = dict(group_name="datasets_health", deps=[
    "datasets_health_nhanes_land", "datasets_health_big_five_land", "datasets_health_who_gho_land",
    "datasets_health_cdc_physical_activity_land", "datasets_health_brfss_land",
    "datasets_health_nhis_land", "datasets_health_usda_fooddata_land", "datasets_health_open_food_facts_land",
])


@asset(**_COMMON, description="Silver — Parquet (batch columnar) for each health raw table.")
def datasets_health_parquet(context) -> Output[dict]:
    return _run_format(context, _write_parquet, _PARQUET_ALLOW)


@asset(**_COMMON, description="Silver — Arrow/Feather (IPC) for each health raw table.")
def datasets_health_arrow(context) -> Output[dict]:
    return _run_format(context, _write_arrow, _ARROW_ALLOW)


@asset(**_COMMON, description="Silver — Avro (row-oriented / streaming) for each health raw table.")
def datasets_health_avro(context) -> Output[dict]:
    return _run_format(context, _write_avro, _AVRO_ALLOW)


@asset(**_COMMON, description="Silver — Lance (ML/vector) for each health raw table — allowlisted per grid. Native Rust S3 writer — isolated.")
def datasets_health_lance(context) -> Output[dict]:
    return _run_format(context, _write_lance, _LANCE_ALLOW)


@asset(**_COMMON, description="Gold — Iceberg table (Nessie, datasets_health.*) for each health raw table.")
def datasets_health_iceberg(context) -> Output[dict]:
    return _run_format(context, _hydrate_iceberg, _ICEBERG_ALLOW)


@asset(
    group_name="datasets_health",
    deps=["datasets_health_parquet", "datasets_health_arrow", "datasets_health_avro", "datasets_health_lance"],
    description="Commit the lakeFS health branch after the file writes → one version per pipeline run. "
    "Iceberg is on Nessie, not lakeFS.",
)
def datasets_health_commit(context) -> Output[dict]:
    import lakefs

    client = lakefs.Client(
        host=os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000"),
        username=os.environ["LAKEFS_ACCESS_KEY_ID"],
        password=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
    )
    branch = lakefs.Repository(_REPO, client=client).branch(_BRANCH)
    changes = list(branch.uncommitted())
    if not changes:
        context.log.info(f"lakeFS {_REPO}/{_BRANCH}: no uncommitted changes — nothing to version")
        return Output({"committed": False, "changes": 0})
    ref = branch.commit(message="datasets_health pipeline run", metadata={"producer": "dagster:datasets_health"})
    commit_id = ref.get_commit().id
    context.log.info(f"lakeFS {_REPO}/{_BRANCH}: committed {len(changes)} change(s) → {commit_id[:12]}")
    return Output(
        {"committed": True, "changes": len(changes), "commit": commit_id},
        metadata={"changes": MetadataValue.int(len(changes)), "commit": MetadataValue.text(commit_id)},
    )
