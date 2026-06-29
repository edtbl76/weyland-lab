"""Last.fm dataset — user listening history, artist tags, play counts via HuggingFace."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land Last.fm listening data → music/raw/lastfm/.")
def datasets_music_lastfm_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    candidates = [
        "logasja/lastfm",
        "rceborg/lastfm-dataset-360K",
        "d0rj/lastfm-tags",
    ]
    for candidate in candidates:
        try:
            context.log.info(f"Last.fm: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, "lastfm/lastfm.csv", data, "text/csv")
            context.log.info(f"Last.fm ({candidate}): {len(ds)} rows → {len(data):,} bytes")
            return Output({"rows": len(ds), "source": candidate}, metadata={"rows": MetadataValue.int(len(ds))})
        except Exception as e:
            context.log.warning(f"Last.fm {candidate}: {e}")
    context.log.warning("Last.fm: no public HuggingFace dataset found")
    return Output({"rows": 0}, metadata={"rows": MetadataValue.int(0)})
