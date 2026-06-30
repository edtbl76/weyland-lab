"""B72 — music dataset fan-out transform (silver + gold), BROKERED as one asset PER format.

Rather than one monolith (where a single bad source read sinks every format), each output format is
its own Dagster asset — datasets_music_parquet / _arrow / _avro / _lance / _iceberg — all depending
on datasets_music_land. Dagster's multiprocess executor runs each in its OWN child process, so a
failure — even a NATIVE crash (e.g. Lance's Rust S3 writer) — is isolated to that format's asset;
the others still land. The asset graph IS the broker.

Source CSVs are read once per asset with newlines_in_values=True (FMA/Spotify cells carry embedded
newlines), and an unreadable file is skipped, not fatal. (Each asset re-reads raw/ — cheap on the LAN
and the price of full process isolation; passing big Arrow tables between assets would lose it.)
"""
import io
import os
import re

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.feather as feather
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset
from minio import Minio


# Write THROUGH the lakeFS S3 gateway (versioned), not MinIO directly. The bucket is the lakeFS repo and
# every key is prefixed with the branch → s3://<repo>/<branch>/<key>. lakeFS stores the bytes in MinIO
# at datasets/music/<branch>/<key>.
_REPO = os.environ.get("LAKEFS_REPO", "music")
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
    """Best-effort custom-emit to DataHub — Arrow/Lance have NO native connector, so they're catalogued
    here. A DataHub hiccup must NOT fail the file write that already succeeded."""
    try:
        from weyland_pipeline.datahub_emit import emit_file_dataset

        emit_file_dataset(platform, table, location, schema, producer)
    except Exception as e:  # noqa: BLE001 — catalog is best-effort; the bytes are already written
        print(f"[datasets_music] DataHub emit {platform}/{table} failed (file written OK): {e}")


_PARSE = pacsv.ParseOptions(newlines_in_values=True)  # FMA/Spotify cells contain embedded newlines


def _sanitize_columns(t):
    """Rename empty/blank column names (e.g. an unnamed CSV index column → "") to column_<i>. DataHub's
    GMS 422-rejects a schemaMetadata aspect with an empty field path. Rename only — no column is dropped."""
    names = t.column_names
    if all(n and n.strip() for n in names):
        return t
    return t.rename_columns([n if (n and n.strip()) else f"column_{i}" for i, n in enumerate(names)])


def _iter_raw_tables(client, bucket, log, allow):
    """Yield (table, name, arrow_table) for each raw CSV whose table is in `allow`. Tables outside the
    allowlist are skipped BEFORE the (possibly large) download+read — gating only the write would still
    pay the read cost (e.g. re-reading lastfm's 14M rows per format just to skip Lance, or a 9GB deferred
    source). An unreadable file is skipped, not fatal."""
    raw_prefix = _k("raw/")
    for obj in client.list_objects(bucket, prefix=raw_prefix, recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        rel = obj.object_name[len(raw_prefix):]      # <table>/<file>.csv
        table = rel.split("/")[0]
        if table not in allow:
            continue
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
        yield table, name, _sanitize_columns(t)


# --- format writers (uniform signature so the broker calls them interchangeably) ---
def _write_parquet(client, bucket, table, name, t):
    buf = io.BytesIO()
    pq.write_table(t, buf)
    _put(client, bucket, f"parquet/{table}/{name}.parquet", buf.getvalue())
    _catalog_file("parquet", table, f"lakefs://{bucket}/{_BRANCH}/parquet/{table}/", t.schema, "datasets_music_parquet")
    _catalog_file("s3", table, f"lakefs://{bucket}/{_BRANCH}/raw/{table}/", t.schema, "datasets_music_land")


def _write_arrow(client, bucket, table, name, t):
    sink = pa.BufferOutputStream()
    feather.write_feather(t, sink)
    _put(client, bucket, f"arrow/{table}/{name}.arrow", sink.getvalue().to_pybytes())
    _catalog_file("arrow", table, f"lakefs://{bucket}/{_BRANCH}/arrow/{table}/", t.schema, "datasets_music_arrow")


_AVRO_TYPE = {"int64": "long", "int32": "int", "double": "double", "float": "float",
              "bool": "boolean", "string": "string", "large_string": "string"}


def _write_avro(client, bucket, table, name, t):
    import fastavro

    fields = [{"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
              for f in t.schema]
    schema = fastavro.parse_schema({"type": "record", "name": f"{table}_record", "fields": fields})
    str_cols = {f.name for f in t.schema
                if _AVRO_TYPE.get(str(f.type), "string") == "string" and str(f.type) not in ("string", "large_string")}

    def _records():
        # Stream record batches so only ~50k rows of Python dicts exist at once. t.to_pylist() on the
        # whole table (lastfm ~14M rows) was a multi-GB spike — a top contributor to the node OOM.
        for batch in t.to_batches(max_chunksize=50_000):
            for r in batch.to_pylist():
                for c in str_cols:
                    if r.get(c) is not None:
                        r[c] = str(r[c])
                yield r

    buf = io.BytesIO()
    fastavro.writer(buf, schema, _records())
    _put(client, bucket, f"avro/{table}/{name}.avro", buf.getvalue())
    _catalog_file("avro", table, f"lakefs://{bucket}/{_BRANCH}/avro/{table}/", t.schema, "datasets_music_avro")


def _write_lance(client, bucket, table, name, t):
    import lance

    uri = f"s3://{bucket}/{_BRANCH}/lance/{table}"
    storage_options = {
        "access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
        "secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        "endpoint": os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000"),
        "allow_http": "true",
        "region": "us-east-1",
    }
    lance.write_dataset(t, uri, mode="overwrite", storage_options=storage_options)
    _catalog_file("lance", table, f"lakefs://{bucket}/{_BRANCH}/lance/{table}/", t.schema, "datasets_music_lance")


# Tables above this skip the inline pyiceberg overwrite — writing a huge table's parquet to the warehouse
# stalls on a network wait with no timeout (usda food_nutrient ~24M rows hung the step for 30m, CPU=0).
# Oversized tables are DEFERRED (still present in parquet/arrow/avro/lance); a dedicated large-table writer
# is the follow-up. 15M clears lastfm (~14M, which committed fine) but defers the genuine monsters. Tune up
# as the warehouse path improves.
_ICEBERG_MAX_ROWS = 15_000_000


class _SkipTable(Exception):
    """Raised by a writer to skip ONE table without marking the whole format errored (e.g. oversized iceberg)."""


def _ice_ident(table, name):
    """Per-file Iceberg table id. The writer used to name the table by FOLDER only, so every file in a
    multi-file folder (usda's 30 CSVs, musicbrainz's 12 splits, audioset train/test) overwrote one table —
    only the last survived. Now each file gets its own table; single-file folders stay as just the folder."""
    base = table if name == table else f"{table}_{name}"
    ident = re.sub(r"[^0-9a-zA-Z]+", "_", base).strip("_").lower()
    return ident if ident and not ident[0].isdigit() else f"t_{ident}"


def _hydrate_iceberg(client, bucket, table, name, t):
    if t.num_rows > _ICEBERG_MAX_ROWS:
        raise _SkipTable(f"{t.num_rows:,} rows > {_ICEBERG_MAX_ROWS:,} cap — deferred from inline Iceberg")
    from weyland_pipeline.iceberg_publish import _catalog

    cat = _catalog()
    # Namespace convention: datasets_<domain> (flat, underscore-separated).
    # Nessie nested namespaces (datasets → music) are NOT visible in Trino catalog.type=nessie —
    # TrinoNessieCatalog.listSchemas() only returns top-level namespaces and there is no config flag
    # to enable recursion (the type=rest fix in Trino 463 does NOT apply to type=nessie). Confirmed
    # broken on Trino 468. SHOW SCHEMAS hides them and queries against "datasets.music" error.
    # Workaround: flat prefixed namespaces (datasets_music, datasets_health) in Nessie/Trino.
    cat.create_namespace_if_not_exists("datasets_music")
    full = f"datasets_music.{_ice_ident(table, name)}"
    ice = cat.create_table_if_not_exists(full, schema=t.schema)
    with ice.update_schema() as update:
        update.union_by_name(t.schema)
    ice = cat.load_table(full)
    ice.overwrite(t)


# --- per-format allowlists (source of truth: docs/data-domain-storage-grid.csv) ---
# Keyed by the raw/ folder name (= rel.split("/")[0]). A table not in a format's allowlist is SKIPPED
# for that format. Parquet/Arrow/Avro/Iceberg are "Y" for every music dataset; Lance is selective —
# the grid marks fma_genres, lastfm, musicbrainz, lp_musiccaps_mc/mtt as N (row-heavy / no embedding
# value — Lance-encoding lastfm's ~14M rows is pure waste). The allowlist also fences out stale raw/
# folders (e.g. the renamed-away msd/, spotify_charts/) so they never leak into the silver/gold layers.
_MUSIC_ALL = {
    "spotify_tracks", "fma_tracks", "fma_genres", "fma_echonest", "fma_features",
    "uci_year_prediction", "lastfm", "musicbrainz", "gtzan",
    "lp_musiccaps_mc", "lp_musiccaps_mtt", "audioset",
}
_PARQUET_ALLOW = _MUSIC_ALL
_ARROW_ALLOW = _MUSIC_ALL
_AVRO_ALLOW = _MUSIC_ALL
_ICEBERG_ALLOW = _MUSIC_ALL
_LANCE_ALLOW = {
    "spotify_tracks", "fma_tracks", "fma_echonest", "fma_features",
    "uci_year_prediction", "gtzan", "audioset",
}


def _run_format(context, write_one, allow) -> Output:
    client = _minio()
    bucket = _REPO
    out: dict = {}
    for table, name, t in _iter_raw_tables(client, bucket, context.log, allow):
        key = f"{table}/{name}"
        try:
            write_one(client, bucket, table, name, t)
            out[key] = f"ok ({t.num_rows}r x {t.num_columns}c)"
        except _SkipTable as sk:
            out[key] = f"deferred: {sk}"
            context.log.warning(f"{key}: deferred — {sk}")
        except Exception as e:  # noqa: BLE001 — per-table resilience within a format
            out[key] = f"ERROR {type(e).__name__}: {e}"
            context.log.error(f"{key}: {e}")
    if not out:
        context.log.warning("no allowlisted raw tables under music/raw/ — run datasets_music_land first")
    return Output(out, metadata={
        "ok": MetadataValue.int(sum(1 for v in out.values() if v.startswith("ok"))),
        "deferred": MetadataValue.int(sum(1 for v in out.values() if v.startswith("deferred"))),
        "detail": MetadataValue.json(out),
    })


_COMMON = dict(group_name="datasets_music", deps=["datasets_music_spotify_land", "datasets_music_fma_tracks_land", "datasets_music_fma_genres_land", "datasets_music_fma_echonest_land"])


@asset(**_COMMON, description="Silver — Parquet (batch columnar) for each music raw table.")
def datasets_music_parquet(context) -> Output[dict]:
    return _run_format(context, _write_parquet, _PARQUET_ALLOW)


@asset(**_COMMON, description="Silver — Arrow/Feather (IPC) for each music raw table.")
def datasets_music_arrow(context) -> Output[dict]:
    return _run_format(context, _write_arrow, _ARROW_ALLOW)


@asset(**_COMMON, description="Silver — Avro (row-oriented / streaming) for each music raw table.")
def datasets_music_avro(context) -> Output[dict]:
    return _run_format(context, _write_avro, _AVRO_ALLOW)


@asset(**_COMMON, description="Silver — Lance (ML/vector) for each music raw table — allowlisted per grid. Native Rust S3 writer — isolated.")
def datasets_music_lance(context) -> Output[dict]:
    return _run_format(context, _write_lance, _LANCE_ALLOW)


@asset(**_COMMON, description="Gold — Iceberg table (Nessie, datasets_music.*) for each music raw table.")
def datasets_music_iceberg(context) -> Output[dict]:
    return _run_format(context, _hydrate_iceberg, _ICEBERG_ALLOW)


@asset(
    group_name="datasets_music",
    deps=["datasets_music_parquet", "datasets_music_arrow", "datasets_music_avro", "datasets_music_lance"],
    description="Commit the lakeFS music branch after file writes → one version per pipeline run.",
)
def datasets_music_commit(context) -> Output[dict]:
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
    ref = branch.commit(message="datasets_music pipeline run", metadata={"producer": "dagster:datasets_music"})
    commit_id = ref.get_commit().id
    context.log.info(f"lakeFS {_REPO}/{_BRANCH}: committed {len(changes)} change(s) → {commit_id[:12]}")
    return Output(
        {"committed": True, "changes": len(changes), "commit": commit_id},
        metadata={"changes": MetadataValue.int(len(changes)), "commit": MetadataValue.text(commit_id)},
    )
