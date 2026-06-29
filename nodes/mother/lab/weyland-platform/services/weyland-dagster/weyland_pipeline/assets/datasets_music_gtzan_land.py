"""GTZAN Genre Collection — 1k songs, 10 genres, canonical genre classification benchmark.
Using the script-free parquet version: ccmusic-database/GTZAN (no trust_remote_code needed).
marsyas/gtzan requires a custom loading script which is an RCE risk — avoided."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put, is_fresh_local


@asset(group_name="datasets_music", description="Land GTZAN genre dataset → music/raw/gtzan/.")
def datasets_music_gtzan_land(context) -> Output[dict]:
    if is_fresh_local(context, max_age_days=30):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    from datasets import load_dataset
    client = music_minio()
    context.log.info("GTZAN: loading confit/gtzan-parquet from HuggingFace")
    ds = load_dataset("confit/gtzan-parquet", split="train")
    # Skip audio decoding — write metadata only (genre label etc.), not raw audio bytes
    skip_cols = {"audio", "video", "file"}
    cols = [c for c in ds.column_names if c not in skip_cols]
    buf = io.StringIO()
    writer = csvmod.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for row in ds.select_columns(cols):
        writer.writerow({k: str(v) for k, v in row.items()})
    data = buf.getvalue().encode("utf-8")
    music_put(client, "gtzan/gtzan.csv", data, "text/csv")
    context.log.info(f"gtzan/gtzan.csv: {len(ds):,} rows → {len(data):,} bytes")
    return Output({"rows": len(ds), "source": "confit/gtzan-parquet"}, metadata={"rows": MetadataValue.int(len(ds))})
