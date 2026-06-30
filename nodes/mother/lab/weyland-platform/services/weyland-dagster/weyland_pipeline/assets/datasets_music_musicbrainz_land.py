"""MusicBrainz — open music encyclopedia via seungheondoh/music-wiki (HuggingFace).
Entity types as splits: artist, release, release_group, work, genre, instrument, label, place, area,
event, series, plus wikipedia_music.

PARQUET-DIRECT (no `load_dataset`). `load_dataset` — even with `streaming=True` — buffers the whole split
into memory, and the 825MB `release` split OOM-killed the 12Gi pod every run. Instead we pull the HF
auto-converted parquet shards directly (datasets-server API → public CDN) and read them in pyarrow
**batches** → a CSV temp file on disk → upload. Memory is bounded to one batch regardless of split size."""
import csv as csvmod
import json
import os
import tempfile
import urllib.request

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_fput, is_fresh_local

_DATASET = "seungheondoh/music-wiki"
_PARQUET_API = f"https://datasets-server.huggingface.co/parquet?dataset={_DATASET}"
_BATCH = 10_000


def _split_parquet_urls(timeout: int = 60) -> dict:
    """Map each split → its list of parquet shard URLs (HF auto-converted, public)."""
    req = urllib.request.Request(_PARQUET_API, headers={"User-Agent": "weyland-datasets-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    by_split: dict = {}
    for f in data.get("parquet_files", []):
        by_split.setdefault(f["split"], []).append(f["url"])
    return by_split


@asset(group_name="datasets_music", description="Land MusicBrainz entities → music/raw/musicbrainz/ (parquet-direct, batched).")
def datasets_music_musicbrainz_land(context) -> Output[dict]:
    if is_fresh_local(context, max_age_days=30):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    client = music_minio()
    by_split = _split_parquet_urls()
    out = {}
    for split, urls in by_split.items():
        csv_path = None
        try:
            context.log.info(f"MusicBrainz: {split} — {len(urls)} parquet shard(s)")
            fd, csv_path = tempfile.mkstemp(suffix=".csv")
            os.close(fd)
            n = 0
            with open(csv_path, "w", newline="", encoding="utf-8") as cf:
                writer = None
                for url in urls:
                    pfd, pq_path = tempfile.mkstemp(suffix=".parquet")
                    os.close(pfd)
                    try:
                        urllib.request.urlretrieve(url, pq_path)
                        for batch in pq.ParquetFile(pq_path).iter_batches(batch_size=_BATCH):
                            rows = batch.to_pylist()
                            if not rows:
                                continue
                            if writer is None:
                                writer = csvmod.DictWriter(cf, fieldnames=list(rows[0].keys()))
                                writer.writeheader()
                            for row in rows:
                                writer.writerow({k: str(v) for k, v in row.items()})
                                n += 1
                    finally:
                        if os.path.exists(pq_path):
                            os.remove(pq_path)
            if n == 0:
                out[split] = 0
                context.log.warning(f"MusicBrainz {split}: no rows")
                continue
            music_fput(client, f"musicbrainz/{split}.csv", csv_path, "text/csv")
            out[split] = n
            context.log.info(f"musicbrainz/{split}.csv: {n:,} rows (batched)")
        except Exception as e:
            out[split] = f"ERROR: {e}"
            context.log.warning(f"MusicBrainz {split}: {e}")
        finally:
            if csv_path and os.path.exists(csv_path):
                os.remove(csv_path)
    total = sum(v for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"total_rows": MetadataValue.int(total), "detail": MetadataValue.json(out)})
