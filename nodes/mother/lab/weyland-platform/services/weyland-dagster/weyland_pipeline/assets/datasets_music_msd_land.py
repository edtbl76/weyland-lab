"""Million Song Dataset (MSD) — HuggingFace subset (full dataset requires AWS snapshot).
Uses the publicly available HuggingFace subset for audio features + metadata."""
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put
import io
import csv as csvmod


@asset(group_name="datasets_music", description="Land Million Song Dataset subset → music/raw/msd/.")
def datasets_music_msd_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    candidates = [
        "msd-unsupervised/msd-audio-features",
        "lewtun/music-genres",
        "maharshipandya/million-song-dataset",
    ]
    for candidate in candidates:
        try:
            context.log.info(f"MSD: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, "msd/msd.csv", data, "text/csv")
            context.log.info(f"MSD ({candidate}): {len(ds)} rows → {len(data):,} bytes")
            return Output({"rows": len(ds), "source": candidate}, metadata={"rows": MetadataValue.int(len(ds))})
        except Exception as e:
            context.log.warning(f"MSD {candidate}: {e}")
    context.log.warning("MSD: no public HuggingFace dataset found")
    return Output({"rows": 0}, metadata={"rows": MetadataValue.int(0)})
