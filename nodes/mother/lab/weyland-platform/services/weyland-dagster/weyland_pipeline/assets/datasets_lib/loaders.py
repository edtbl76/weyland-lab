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


def build_store_load_assets(cfg):
    """Return the per-store loader assets this domain needs (only stores with a non-empty allowlist)."""
    assets = []
    d = cfg.domain

    if cfg.mysql_allow:
        @asset(
            name=f"datasets_{d}_mysql_load",
            group_name=cfg.group_name,
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

    return assets
