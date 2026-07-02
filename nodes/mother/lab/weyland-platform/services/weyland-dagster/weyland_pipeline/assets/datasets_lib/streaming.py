"""Streamed silver — for one raw object too big to read whole. The broker reads each raw object into a
single Arrow table, which OOMs on open_food_facts (a ~9GB-decompressed, 211-column, tab-separated products
export). This streams it instead: minio streaming get → gzip streaming decompress → pandas chunked read
(all-string — OFF is sparse + type-mixed across 200+ columns, so forcing str avoids type-inference blowups
mid-stream) → ParquetWriter appending each chunk to a temp file → fput (streamed upload) to lakeFS. Memory is
bounded to one chunk. Parquet only — the silver format the store loaders read; the other formats stay
deferred for a source this size. The dataset stays in the broker's _DEFERRED (it can't read it whole)."""
import gzip
import os
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from . import io
from .readers import sanitize_columns
from .writers import _loc, catalog_file


def build_streamed_parquet_asset(cfg, dataset, raw_object, sep="\t", chunksize=50_000):
    """A dedicated asset that streams one big compressed delimited raw object → silver parquet. Named
    datasets_<domain>_<dataset>_parquet, distinct from the broker's datasets_<domain>_parquet."""

    @asset(
        name=f"datasets_{cfg.domain}_{dataset}_parquet",
        group_name=cfg.group_name,
        deps=list(cfg.land_deps),
        description=f"Silver — Parquet (streamed, chunked) for {dataset}: too big to read whole (broker OOMs).",
    )
    def _streamed(context):
        import pandas as pd

        mc = io.client()
        key = f"{io.raw_prefix()}{dataset}/{raw_object}"
        resp = mc.get_object(cfg.repo, key)
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        writer, rows, schema = None, 0, None
        try:
            gz = gzip.GzipFile(fileobj=resp)   # streaming decompress — never holds the whole file
            for chunk in pd.read_csv(gz, sep=sep, dtype=str, na_filter=False,
                                     chunksize=chunksize, on_bad_lines="warn"):
                t = sanitize_columns(pa.Table.from_pandas(chunk, preserve_index=False))
                if writer is None:
                    schema = t.schema
                    writer = pq.ParquetWriter(tmp.name, schema)
                writer.write_table(t)
                rows += len(chunk)
                if rows % (chunksize * 20) == 0:
                    context.log.info(f"{dataset}: {rows:,} rows streamed")
        finally:
            if writer is not None:
                writer.close()
            resp.close()
            resp.release_conn()
        dest = f"parquet/{dataset}/{dataset}.parquet"
        io.fput(mc, cfg.repo, dest, tmp.name)   # streamed upload — parquet never held in memory
        os.unlink(tmp.name)
        context.log.info(f"{dataset}: {rows:,} rows → {cfg.repo}/{io.branch()}/{dest}")
        # catalog for DataHub (parquet + raw), same as the broker's write_parquet
        if schema is not None:
            catalog_file(cfg.domain, "parquet", dataset, _loc(cfg, "parquet", dataset), schema, f"{cfg.producer}_parquet")
            catalog_file(cfg.domain, "s3", dataset, _loc(cfg, "raw", dataset), schema, f"{cfg.producer}_land")
        return Output({dataset: rows}, metadata={
            "rows": MetadataValue.int(rows),
            "columns": MetadataValue.int(len(schema) if schema else 0),
            "dest": MetadataValue.text(dest),
        })

    return _streamed
