"""MusicBrainz — open music encyclopedia via seungheondoh/music-wiki (HuggingFace).
Multiple configs: artist, release, release_group, work, genre, instrument, label, place, area, event, series."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put, is_fresh_local


SPLITS = [
    "musicbrainz_artist", "musicbrainz_release", "musicbrainz_release_group",
    "musicbrainz_work", "musicbrainz_genre", "musicbrainz_instrument",
    "musicbrainz_label", "musicbrainz_place", "musicbrainz_area",
    "musicbrainz_event", "musicbrainz_series", "wikipedia_music",
]


@asset(group_name="datasets_music", description="Land MusicBrainz entities → music/raw/musicbrainz/.")
def datasets_music_musicbrainz_land(context) -> Output[dict]:
    if is_fresh_local(context, max_age_days=30):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    from datasets import load_dataset
    client = music_minio()
    out = {}
    for split in SPLITS:
        try:
            context.log.info(f"MusicBrainz: loading split {split}")
            ds = load_dataset("seungheondoh/music-wiki", split=split)
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow({k: str(v) for k, v in row.items()})
            data = buf.getvalue().encode("utf-8")
            music_put(client, f"musicbrainz/{split}.csv", data, "text/csv")
            out[split] = len(ds)
            context.log.info(f"musicbrainz/{split}.csv: {len(ds):,} rows → {len(data):,} bytes")
        except Exception as e:
            out[split] = f"ERROR: {e}"
            context.log.warning(f"MusicBrainz {split}: {e}")
    total = sum(v for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"total_rows": MetadataValue.int(total), "detail": MetadataValue.json(out)})
