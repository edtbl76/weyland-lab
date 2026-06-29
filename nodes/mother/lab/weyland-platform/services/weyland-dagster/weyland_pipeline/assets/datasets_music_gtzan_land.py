"""GTZAN Genre Collection — 1k songs, 10 genres, canonical genre classification benchmark.
Source: marsyas/gtzan on HuggingFace."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land GTZAN genre dataset → music/raw/gtzan/.")
def datasets_music_gtzan_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("GTZAN: loading marsyas/gtzan from HuggingFace")
    ds = load_dataset("marsyas/gtzan", split="train")
    buf = io.StringIO()
    # Write metadata only (not audio bytes) — genre label + file path
    writer = csvmod.DictWriter(buf, fieldnames=[c for c in ds.column_names if c != "audio"])
    writer.writeheader()
    for row in ds:
        writer.writerow({k: v for k, v in row.items() if k != "audio"})
    data = buf.getvalue().encode("utf-8")
    music_put(client, "gtzan/gtzan.csv", data, "text/csv")
    context.log.info(f"gtzan/gtzan.csv: {len(ds):,} rows → {len(data):,} bytes")
    return Output({"rows": len(ds)}, metadata={"rows": MetadataValue.int(len(ds))})
