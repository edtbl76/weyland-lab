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
    candidates = [
        "ccmusic-database/GTZAN",
        "rudraparmar123/GTZAN-Music-Genre",
        "nazimali/music-genres-dataset",
    ]
    for candidate in candidates:
        try:
            context.log.info(f"GTZAN: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            cols = [c for c in ds.column_names if c != "audio"]
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=cols)
            writer.writeheader()
            for row in ds:
                writer.writerow({k: str(v) for k, v in row.items() if k in cols})
            data = buf.getvalue().encode("utf-8")
            music_put(client, "gtzan/gtzan.csv", data, "text/csv")
            context.log.info(f"gtzan/gtzan.csv ({candidate}): {len(ds):,} rows → {len(data):,} bytes")
            return Output({"rows": len(ds), "source": candidate}, metadata={"rows": MetadataValue.int(len(ds))})
        except Exception as e:
            context.log.warning(f"GTZAN {candidate}: {e}")
    context.log.warning("GTZAN: no script-free dataset found")
    return Output({"rows": 0}, metadata={"rows": MetadataValue.int(0)})
