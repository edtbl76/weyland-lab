"""Format writers — one Arrow table → one output per format. Uniform signature write(mc, cfg, table,
name, t) so the broker calls them interchangeably; each format is its own Dagster asset (own process)
so a failure (even a native Lance Rust-S3 crash) is isolated. All write THROUGH the lakeFS S3 gateway
except Iceberg, which lands on the Nessie warehouse. DataHub catalog emits are best-effort."""
import io as _io
import os
import re

import pyarrow as pa
import pyarrow.feather as feather
import pyarrow.parquet as pq

from . import io
from .readers import coerce_null_cols

# Tables above this skip the inline pyiceberg overwrite — writing a huge table's parquet to the warehouse
# stalls on a network wait with no timeout (usda food_nutrient ~24M rows hung the step 30m, CPU=0).
# Oversized tables DEFER (still present in parquet/arrow/avro/lance); a dedicated large-table writer is the
# follow-up. 15M clears lastfm (~14M, committed fine) but defers the genuine monsters. Tune as infra improves.
ICEBERG_MAX_ROWS = 15_000_000


class SkipTable(Exception):
    """Raised by a writer to skip ONE table without marking the whole format errored (e.g. oversized iceberg)."""


def catalog_file(domain, platform, table, location, schema, producer):
    """Best-effort custom-emit to DataHub — Arrow/Lance have NO native connector. A DataHub hiccup must
    NOT fail the file write that already succeeded."""
    try:
        from weyland_pipeline.datahub_emit import emit_file_dataset

        emit_file_dataset(platform, table, location, schema, producer)
    except Exception as e:  # noqa: BLE001 — catalog is best-effort; the bytes are already written
        print(f"[datasets_{domain}] DataHub emit {platform}/{table} failed (file written OK): {e}")


def _loc(cfg, fmt, table):
    return f"lakefs://{cfg.repo}/{io.branch()}/{fmt}/{table}/"


def write_parquet(mc, cfg, table, name, t):
    buf = _io.BytesIO()
    pq.write_table(t, buf)
    io.put(mc, cfg.repo, f"parquet/{table}/{name}.parquet", buf.getvalue())
    catalog_file(cfg.domain, "parquet", table, _loc(cfg, "parquet", table), t.schema, f"{cfg.producer}_parquet")
    catalog_file(cfg.domain, "s3", table, _loc(cfg, "raw", table), t.schema, f"{cfg.producer}_land")


def write_arrow(mc, cfg, table, name, t):
    sink = pa.BufferOutputStream()
    feather.write_feather(t, sink)
    io.put(mc, cfg.repo, f"arrow/{table}/{name}.arrow", sink.getvalue().to_pybytes())
    catalog_file(cfg.domain, "arrow", table, _loc(cfg, "arrow", table), t.schema, f"{cfg.producer}_arrow")


_AVRO_TYPE = {"int64": "long", "int32": "int", "double": "double", "float": "float",
              "bool": "boolean", "string": "string", "large_string": "string"}


def write_avro(mc, cfg, table, name, t):
    import fastavro

    fields = [{"name": f.name, "type": ["null", _AVRO_TYPE.get(str(f.type), "string")], "default": None}
              for f in t.schema]
    schema = fastavro.parse_schema({"type": "record", "name": re.sub(r"[^0-9a-zA-Z_]", "_", f"{table}_{name}_record"), "fields": fields})
    str_cols = {f.name for f in t.schema
                if _AVRO_TYPE.get(str(f.type), "string") == "string" and str(f.type) not in ("string", "large_string")}

    def _records():
        # Stream record batches so only ~50k rows of Python dicts exist at once. t.to_pylist() on the whole
        # table (lastfm ~14M rows) was a multi-GB spike — a top contributor to the node OOM.
        for batch in t.to_batches(max_chunksize=50_000):
            for r in batch.to_pylist():
                for c in str_cols:
                    if r.get(c) is not None:
                        r[c] = str(r[c])
                yield r

    buf = _io.BytesIO()
    fastavro.writer(buf, schema, _records())
    io.put(mc, cfg.repo, f"avro/{table}/{name}.avro", buf.getvalue())
    catalog_file(cfg.domain, "avro", table, _loc(cfg, "avro", table), t.schema, f"{cfg.producer}_avro")


def write_lance(mc, cfg, table, name, t):
    import lance

    # Per-file path (…/lance/<table>/<name>) so multi-file folders (audioset train/test) don't overwrite
    # one dataset — the same clobber class fixed for iceberg.
    uri = f"s3://{cfg.repo}/{io.branch()}/lance/{table}/{name}"
    storage_options = {
        "access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
        "secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        "endpoint": io.endpoint(),
        "allow_http": "true",
        "region": "us-east-1",
    }
    lance.write_dataset(t, uri, mode="overwrite", storage_options=storage_options)
    catalog_file(cfg.domain, "lance", table, _loc(cfg, "lance", table), t.schema, f"{cfg.producer}_lance")


def ice_ident(table, name):
    """Per-file Iceberg table id. Naming by FOLDER only made every file in a multi-file folder (usda's 30
    CSVs, musicbrainz's 12 splits, audioset train/test) overwrite one table — only the last survived. Now
    each file gets its own table; single-file folders stay as just the folder."""
    base = table if name == table else f"{table}_{name}"
    ident = re.sub(r"[^0-9a-zA-Z]+", "_", base).strip("_").lower()
    return ident if ident and not ident[0].isdigit() else f"t_{ident}"


def hydrate_iceberg(mc, cfg, table, name, t):
    if t.num_rows > ICEBERG_MAX_ROWS:
        raise SkipTable(f"{t.num_rows:,} rows > {ICEBERG_MAX_ROWS:,} cap — deferred from inline Iceberg")
    t = coerce_null_cols(t)
    from weyland_pipeline.iceberg_publish import _catalog

    cat = _catalog()
    # Flat prefixed namespace (datasets_<domain>) — Nessie nested namespaces are invisible to Trino
    # catalog.type=nessie (TrinoNessieCatalog.listSchemas() only returns top-level; no recursion flag;
    # the type=rest fix in Trino 463 does NOT apply to type=nessie — confirmed broken on Trino 468).
    cat.create_namespace_if_not_exists(cfg.namespace)
    full = f"{cfg.namespace}.{ice_ident(table, name)}"
    ice = cat.create_table_if_not_exists(full, schema=t.schema)
    with ice.update_schema() as update:
        update.union_by_name(t.schema)
    ice = cat.load_table(full)
    ice.overwrite(t)
