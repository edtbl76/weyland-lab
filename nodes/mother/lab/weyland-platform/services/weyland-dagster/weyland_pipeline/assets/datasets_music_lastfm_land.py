"""Last.fm — user listening history, artist tags, play counts.
Source: matthewfranglen/lastfm-360k (13.9M rows: user, artist, play_count)."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land Last.fm 360k listening data → music/raw/lastfm/.")
def datasets_music_lastfm_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("Last.fm: loading matthewfranglen/lastfm-360k from HuggingFace (~13.9M rows)")
    ds = load_dataset("matthewfranglen/lastfm-360k", split="train")
    buf = io.StringIO()
    writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
    writer.writeheader()
    for row in ds:
        writer.writerow(row)
    data = buf.getvalue().encode("utf-8")
    music_put(client, "lastfm/lastfm.csv", data, "text/csv")
    context.log.info(f"lastfm/lastfm.csv: {len(ds):,} rows → {len(data):,} bytes")
    return Output({"rows": len(ds), "source": "matthewfranglen/lastfm-360k"}, metadata={"rows": MetadataValue.int(len(ds))})
