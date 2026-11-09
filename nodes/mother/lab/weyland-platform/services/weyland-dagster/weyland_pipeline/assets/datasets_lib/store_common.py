"""Shared pieces of the store loaders (loaders.py and the store_* modules): identifier safety, walking a dataset's
silver Parquet files, the temp-file download every memory-safe loader uses, and per-file resilience.

Identifiers (db / keyspace / table / column names) come from dataset config and are INTERPOLATED into SQL, CQL and
Cypher, because identifiers can't be bound as parameters. `_safe_ident` allowlists a bare identifier and `_q` escapes a
double-quoted one (B47 hardening).
"""
import os
import re
import tempfile
import urllib.parse
from contextlib import contextmanager

from . import io

PARQUET = ".parquet"


def _safe_ident(name):
    """Allowlist a bare SQL identifier before it is interpolated into a statement. Raises on anything with quotes,
    semicolons or whitespace. Call sites pass config-defined snake_case names, so this never fires in practice."""
    n = str(name)
    if n and all(c.isalnum() or c == "_" for c in n):
        return n
    raise ValueError(f"unsafe SQL identifier: {name!r}")


def _q(name):
    """Escape a double-quoted SQL identifier (dataset COLUMN names, which can vary) by doubling quotes."""
    return str(name).replace('"', '""')


def _sql_ident(name: str) -> str:
    """A clean table identifier: non-[A-Za-z0-9_] → _, lower-cased, with a digit-leading guard."""
    s = re.sub(r"\W+", "_", name, flags=re.ASCII).strip("_").lower()   # ASCII: \W == [^0-9A-Za-z_]
    return s if s and not s[0].isdigit() else f"t_{s}"


def lakefs_base():
    """(scheme, base URL) of the lakeFS S3 gateway, taken from the configured endpoint (which always names its
    scheme): the s3() table function and LanceDB address the gateway directly."""
    parts = urllib.parse.urlsplit(io.endpoint())
    return parts.scheme, f"{parts.scheme}://{parts.netloc}"


def parquet_objects(mc, cfg, dataset):
    """Yield (object_name, file_stem) for every silver Parquet file under parquet/<dataset>/ on the current branch."""
    prefix = f"{io.branch()}/parquet/{dataset}/"
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if obj.object_name.endswith(PARQUET):
            yield obj.object_name, obj.object_name.split("/")[-1][: -len(PARQUET)]


def file_table(dataset, stem):
    """The per-file table / collection / index name: the dataset name for its main file, else dataset_<file>."""
    return _sql_ident(dataset if stem == dataset else f"{dataset}_{stem}")


@contextmanager
def downloaded(mc, cfg, object_name):
    """Stream one object to a temp file (not RAM: OFF is 1.63 GB and a whole-object fetch OOMKilled the pod) and
    remove it afterwards, whatever happens."""
    tmp = tempfile.NamedTemporaryFile(suffix=PARQUET, delete=False)
    tmp.close()
    try:
        mc.fget_object(cfg.repo, object_name, tmp.name)
        yield tmp.name
    finally:
        os.unlink(tmp.name)


def record(out, key, label, log, load):
    """Run one file's load and record its count under `key`. A failure is recorded as "ERROR: ..." and logged as
    "<label>: <error>", never raised: one bad table must not stop the rest of the dataset."""
    try:
        out[key] = load()
    except Exception as e:  # noqa: BLE001 - per-file resilience
        out[key] = f"ERROR: {e}"
        log.error(f"{label}: {e}")
