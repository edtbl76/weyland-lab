"""MusicBrainz — open music encyclopedia via seungheondoh/music-wiki (HuggingFace).
Multiple configs: artist, release, release_group, work, genre, instrument, label, place, area, event, series."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land MusicBrainz entities → music/raw/musicbrainz/.")
def datasets_music_musicbrainz_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    context.log.info("MusicBrainz: loading seungheondoh/music-wiki (default config)")
    ds = load_dataset("seungheondoh/music-wiki", split="train")
    context.log.info(f"MusicBrainz columns: {ds.column_names}")
    buf = io.StringIO()
    writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
    writer.writeheader()
    for row in ds:
        writer.writerow({k: str(v) for k, v in row.items()})
    data = buf.getvalue().encode("utf-8")
    music_put(client, "musicbrainz/musicbrainz.csv", data, "text/csv")
    context.log.info(f"musicbrainz/musicbrainz.csv: {len(ds):,} rows → {len(data):,} bytes")
    return Output({"rows": len(ds)}, metadata={"total_rows": MetadataValue.int(len(ds))})
