"""GTZAN Genre Collection — 1k songs, 10 genres, canonical genre classification benchmark.
Using the script-free parquet version: ccmusic-database/GTZAN (no trust_remote_code needed).
marsyas/gtzan requires a custom loading script which is an RCE risk — avoided."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land GTZAN genre dataset → music/raw/gtzan/.")
def datasets_music_gtzan_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("GTZAN: loading confit/gtzan-parquet from HuggingFace")
    ds = load_dataset("confit/gtzan-parquet", split="train")
    audio_cols = [c for c in ds.column_names if c in ("audio", "file", "video")]
    if audio_cols:
        ds = ds.remove_columns(audio_cols)
    buf = io.StringIO()
    writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
    writer.writeheader()
    for row in ds:
        writer.writerow({k: str(v) for k, v in row.items()})
    data = buf.getvalue().encode("utf-8")
    music_put(client, "gtzan/gtzan.csv", data, "text/csv")
    context.log.info(f"gtzan/gtzan.csv: {len(ds):,} rows → {len(data):,} bytes")
    return Output({"rows": len(ds), "source": "confit/gtzan-parquet"}, metadata={"rows": MetadataValue.int(len(ds))})
