"""Readers — turn each raw object into one Arrow table, dispatching on extension. A single reader serves
every domain: music lands only .csv, health adds .xpt (SAS, already rectangular — just needs a reader),
.json (WHO GHO OData {"value":[...]}, nested types kept as-is), and .csv.gz. No flattening — Arrow/Parquet/
Avro carry nested types natively. Unreadable / unknown-extension objects are skipped, not fatal."""
import gzip
import io as _io
import json
import re

import pyarrow as pa
import pyarrow.csv as pacsv

from . import io

_PARSE = pacsv.ParseOptions(newlines_in_values=True)  # FMA/Spotify/etc. cells carry embedded newlines
_EXT_RE = re.compile(r"\.(csv\.gz|csv|xpt|json)$", re.IGNORECASE)


_INVALID_NAME = re.compile(r"[^0-9A-Za-z_]")


def sanitize_columns(t):
    """Normalize every column name to a valid identifier so all formats accept the schema. Names that are
    empty (an unnamed CSV index column → "") or carry characters outside [A-Za-z0-9_] break the strict
    writers: avro rejects empty/special names, Lance rejects '.' (seen on an FMA header where a URL leaked
    into a column name — album_url_http://…), and Iceberg's avro-encoded manifests reject empty. DataHub's
    GMS also 422-rejects an empty field path. Replace invalid chars with '_', guard leading digits, fill
    blanks with column_<i>, and de-duplicate collisions. Rename only — no data is dropped."""
    names = t.column_names
    fixed = []
    for i, n in enumerate(names):
        s = _INVALID_NAME.sub("_", n or "").strip("_")
        if not s:
            s = f"column_{i}"
        elif s[0].isdigit():
            s = f"col_{s}"
        fixed.append(s)
    seen, out = {}, []  # de-dup any collisions introduced by normalization
    for s in fixed:
        if s in seen:
            seen[s] += 1
            out.append(f"{s}_{seen[s]}")
        else:
            seen[s] = 0
            out.append(s)
    return t if out == names else t.rename_columns(out)


def coerce_null_cols(t):
    """Iceberg format-v2 rejects all-null (pa.null()) columns — pyarrow types an entirely-empty source
    column as null (WHO GHO unused Dim*Type, NHIS unused flags, some usda cols). Cast them to string
    (values stay null) so the table is writable. Iceberg-only; parquet/arrow/avro handle null natively."""
    fields = [pa.field(f.name, pa.string()) if pa.types.is_null(f.type) else f for f in t.schema]
    new = pa.schema(fields)
    return t.cast(new) if new != t.schema else t


def read_to_table(rel, data, log):
    """Read one raw object into an Arrow table by extension (case-insensitive). None = skip."""
    low = rel.lower()
    try:
        if low.endswith(".csv.gz"):
            return pacsv.read_csv(_io.BytesIO(gzip.decompress(data)), parse_options=_PARSE)
        if low.endswith(".csv"):
            return pacsv.read_csv(_io.BytesIO(data), parse_options=_PARSE)
        if low.endswith(".xpt"):
            import pandas as pd

            df = pd.read_sas(_io.BytesIO(data), format="xport")
            for c in df.select_dtypes(include=["object"]).columns:
                df[c] = df[c].map(lambda v: v.decode("utf-8", "replace").strip() if isinstance(v, (bytes, bytearray)) else v)
            return pa.Table.from_pandas(df, preserve_index=False)
        if low.endswith(".json"):
            obj = json.loads(data)
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


def iter_raw_tables(mc, repo, allow, log):
    """Yield (table, name, arrow_table) for each readable raw object whose table is in `allow`. Tables
    outside the allowlist are skipped BEFORE the download+read — critical so deferred big sources
    (open_food_facts ~9GB) and per-format exclusions (lastfm for Lance) never pay the read cost.
    table = top-level folder; name = path within the table (slashes → underscores, extension stripped),
    so nested layouts like nhanes/2017-2020/DEMO_J.XPT stay distinct."""
    prefix = io.raw_prefix()
    for obj in mc.list_objects(repo, prefix=prefix, recursive=True):
        rel = obj.object_name[len(prefix):]
        table = rel.split("/")[0]
        if table not in allow:
            continue
        t = read_to_table(rel, io.fetch(mc, repo, obj.object_name), log)
        if t is None:
            continue
        name = _EXT_RE.sub("", rel[len(table) + 1:]).replace("/", "_")
        yield table, name, sanitize_columns(t)
