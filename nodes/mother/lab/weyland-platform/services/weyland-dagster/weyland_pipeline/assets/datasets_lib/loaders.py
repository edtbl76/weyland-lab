"""Store hydration (data-store-mageddon) — the third datasets_lib factory. build_store_load_assets(cfg)
reads silver Parquet from lakeFS and loads it into the Tier-2 stores the grid targets, one loader asset
per store, driven by the explicit per-store allowlists on DomainConfig (a store gets an asset only when
its allowlist is non-empty).

MySQL (always-on, data-mesh ns): dataset → database (pre-created), each parquet file → a table. Written
batched (pyarrow iter_batches → pandas → to_sql append) so big tables (brfss ~3M rows) stay memory-bounded.
"""
import io as _io
import os
import re
import urllib.parse

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from . import io

_MYSQL_BATCH = 50_000
# Mongo docs are Python dicts (heavy — OFF is 211 all-string cols), so a smaller batch than MySQL's, and
# the parquet is read from a temp FILE (not held in RAM) — the 50k+whole-file approach OOMKilled user-code.
_MONGO_BATCH = 20_000


def _sql_ident(name: str) -> str:
    """A clean MySQL table identifier — non-[A-Za-z0-9_] → _, digit-leading guard."""
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_").lower()
    return s if s and not s[0].isdigit() else f"t_{s}"


def _mysql_engine_factory():
    import sqlalchemy

    host = os.environ.get("MYSQL_HOST", "mysql.data-mesh.svc.cluster.local")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    pw = urllib.parse.quote_plus(os.environ["MYSQL_PASSWORD"])
    cache = {}

    def engine_for(db):
        if db not in cache:
            cache[db] = sqlalchemy.create_engine(f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}")
        return cache[db]

    return engine_for


def _load_dataset_to_mysql(mc, cfg, dataset, engine_for, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in MySQL db <dataset>."""
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        table = _sql_ident(obj.object_name.split("/")[-1][: -len(".parquet")])
        try:
            data = io.fetch(mc, cfg.repo, obj.object_name)
            engine = engine_for(dataset)
            n, first = 0, True
            for batch in pq.ParquetFile(_io.BytesIO(data)).iter_batches(batch_size=_MYSQL_BATCH):
                df = batch.to_pandas()
                # default method (executemany), NOT method="multi": a multi-row INSERT compiles
                # chunksize×columns bind params, which is pathologically slow on wide tables (big_five's
                # 57 cols × 5000 = 285k params hung the compile until the run was killed).
                df.to_sql(table, engine, if_exists="replace" if first else "append",
                          index=False, chunksize=1_000)
                first, n = False, n + len(df)
            out[f"{dataset}.{table}"] = n
            log.info(f"mysql {dataset}.{table}: {n:,} rows")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[f"{dataset}.{table}"] = f"ERROR: {e}"
            log.error(f"mysql {dataset}.{table}: {e}")
    return out


def _tsdb_engine():
    import sqlalchemy

    host = os.environ.get("TIMESCALEDB_HOST", "timescaledb.data-mesh.svc.cluster.local")
    port = os.environ.get("TIMESCALEDB_PORT", "5432")
    db = os.environ.get("TIMESCALEDB_DB", "timeseries")
    user = os.environ.get("TIMESCALEDB_USER", "weyland")
    pw = urllib.parse.quote_plus(os.environ.get("TIMESCALEDB_PASSWORD", "weyland_dev_password"))
    return sqlalchemy.create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}")


def _load_dataset_to_timescale(mc, cfg, dataset, time_col, engine, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a TimescaleDB hypertable in db `timeseries`,
    partitioned on a derived `ts` timestamptz. WHO GHO's TimeDim is a year → Jan 1 of that year. Rows with
    no usable year are dropped (a hypertable's time column must be non-null). Table name is dataset-prefixed
    (who_gho_<indicator>) since TimescaleDB is one flat db — mirrors the Iceberg/DuckDB per-file naming."""
    import pandas as pd
    import sqlalchemy

    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        table = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        try:
            data = io.fetch(mc, cfg.repo, obj.object_name)
            df = pq.ParquetFile(_io.BytesIO(data)).read().to_pandas()
            if time_col not in df.columns:
                raise KeyError(f"time column {time_col!r} not in {list(df.columns)[:10]}")
            df["ts"] = pd.to_datetime(df[time_col], format="%Y", errors="coerce", utc=True)
            df = df[df["ts"].notna()]
            df.to_sql(table, engine, if_exists="replace", index=False, chunksize=5_000)
            # to_sql made a plain table (dropping any prior hypertable); (re)promote it. migrate_data moves
            # the just-loaded rows into chunks; if_not_exists keeps it idempotent across re-runs.
            with engine.begin() as conn:
                conn.execute(sqlalchemy.text(
                    f"SELECT create_hypertable('{table}', 'ts', if_not_exists => TRUE, migrate_data => TRUE)"))
            out[table] = int(len(df))
            log.info(f"timescaledb {table}: {len(df):,} rows → hypertable on ts (from {time_col})")
        except Exception as e:  # noqa: BLE001 — per-table resilience
            out[table] = f"ERROR: {e}"
            log.error(f"timescaledb {table}: {e}")
    return out


def _mongo_client():
    from pymongo import MongoClient

    host = os.environ.get("MONGO_HOST", "mongodb.data-mesh.svc.cluster.local")
    port = os.environ.get("MONGO_PORT", "27017")
    user = urllib.parse.quote_plus(os.environ.get("MONGO_USER", "weyland"))
    pw = urllib.parse.quote_plus(os.environ.get("MONGO_PASSWORD", "weyland_dev_password"))
    return MongoClient(f"mongodb://{user}:{pw}@{host}:{port}/?authSource=admin")


def _load_dataset_to_mongo(mc, cfg, dataset, client, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a Mongo collection in db datasets_<domain>,
    doc per row. MEMORY-SAFE: the parquet is DOWNLOADED TO A TEMP FILE (not held in RAM — OFF is 1.63GB and
    io.fetch-whole OOMKilled the pod) and read in row batches → insert_many, freeing each batch. Collection
    dropped + reloaded each run (idempotent). Names mirror the per-file convention."""
    import tempfile

    db = client[f"datasets_{cfg.domain}"]
    prefix = f"{io.branch()}/parquet/{dataset}/"
    out = {}
    for obj in mc.list_objects(cfg.repo, prefix=prefix, recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        fname = obj.object_name.split("/")[-1][: -len(".parquet")]
        coll = _sql_ident(dataset if fname == dataset else f"{dataset}_{fname}")
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            db[coll].drop()
            mc.fget_object(cfg.repo, obj.object_name, tmp.name)   # streamed download to disk, not RAM
            n = 0
            for batch in pq.ParquetFile(tmp.name).iter_batches(batch_size=_MONGO_BATCH):
                docs = batch.to_pylist()
                if docs:
                    db[coll].insert_many(docs, ordered=False)
                    n += len(docs)
                del batch, docs
            out[coll] = n
            log.info(f"mongo datasets_{cfg.domain}.{coll}: {n:,} docs")
        except Exception as e:  # noqa: BLE001 — per-collection resilience
            out[coll] = f"ERROR: {e}"
            log.error(f"mongo {coll}: {e}")
        finally:
            os.unlink(tmp.name)
    return out


def build_store_load_assets(cfg):
    """Return the per-store loader assets this domain needs (only stores with a non-empty allowlist)."""
    assets = []
    d = cfg.domain

    if cfg.mysql_allow:
        @asset(
            name=f"datasets_{d}_mysql_load",
            group_name=f"datasets_{d}_stores",  # own group — NOT the transform group, so the transform job won't run it
            deps=[f"datasets_{d}_parquet"],  # reads silver after it exists; parquet's no_failures check gates it
            description=f"Hydrate MySQL from silver Parquet — db per dataset, table per file ({len(cfg.mysql_allow)} datasets).",
        )
        def _mysql_load(context):
            mc = io.client()
            engine_for = _mysql_engine_factory()
            out = {}
            for dataset in sorted(cfg.mysql_allow):
                out.update(_load_dataset_to_mysql(mc, cfg, dataset, engine_for, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "tables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_mysql_load)

    if cfg.timescale_allow:
        @asset(
            name=f"datasets_{d}_timescaledb_load",
            group_name=f"datasets_{d}_stores",   # same stores group → runs in the hydrate job, not the transform
            deps=[f"datasets_{d}_parquet"],       # gated by the parquet no_failures check
            description=f"Hydrate TimescaleDB hypertables from silver Parquet ({len(cfg.timescale_allow)} dataset(s)).",
        )
        def _timescale_load(context):
            mc = io.client()
            engine = _tsdb_engine()
            out = {}
            for dataset, time_col in sorted(cfg.timescale_allow.items()):
                out.update(_load_dataset_to_timescale(mc, cfg, dataset, time_col, engine, context.log))
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "hypertables_loaded": MetadataValue.int(ok),
                "rows_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_timescale_load)

    if cfg.mongo_allow:
        # datasets from the broker's parquet + any that come from a dedicated streamed asset (OFF)
        _mongo_deps = [f"datasets_{d}_parquet"] + [
            f"datasets_{d}_{ds}_parquet" for ds in sorted(cfg.mongo_allow & cfg.streamed_parquet)]

        @asset(
            name=f"datasets_{d}_mongodb_load",
            group_name=f"datasets_{d}_stores",
            deps=_mongo_deps,
            description=f"Hydrate MongoDB collections from silver Parquet ({len(cfg.mongo_allow)} datasets).",
        )
        def _mongo_load(context):
            mc = io.client()
            client = _mongo_client()
            out = {}
            try:
                for dataset in sorted(cfg.mongo_allow):
                    out.update(_load_dataset_to_mongo(mc, cfg, dataset, client, context.log))
            finally:
                client.close()
            ok = sum(1 for v in out.values() if isinstance(v, int))
            return Output(out, metadata={
                "collections_loaded": MetadataValue.int(ok),
                "docs_total": MetadataValue.int(sum(v for v in out.values() if isinstance(v, int))),
                "detail": MetadataValue.json(out),
            })

        assets.append(_mongo_load)

    return assets
