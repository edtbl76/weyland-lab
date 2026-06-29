"""MusicBrainz — open music encyclopedia via seungheondoh/music-wiki (HuggingFace).
Multiple configs: artist, release, release_group, work, genre, instrument, label, place, area, event, series."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


CONFIGS = [
    "musicbrainz_artist",
    "musicbrainz_release",
    "musicbrainz_release_group",
    "musicbrainz_work",
    "musicbrainz_genre",
    "musicbrainz_instrument",
    "musicbrainz_label",
    "musicbrainz_place",
    "musicbrainz_area",
    "musicbrainz_event",
    "musicbrainz_series",
]


@asset(group_name="datasets_music", description="Land MusicBrainz entities → music/raw/musicbrainz/.")
def datasets_music_musicbrainz_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    out = {}
    for config in CONFIGS:
        try:
            context.log.info(f"MusicBrainz: loading {config}")
            ds = load_dataset("seungheondoh/music-wiki", config, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, f"musicbrainz/{config}.csv", data, "text/csv")
            out[config] = len(ds)
            context.log.info(f"musicbrainz/{config}.csv: {len(ds):,} rows → {len(data):,} bytes")
        except Exception as e:
            out[config] = f"ERROR: {e}"
            context.log.warning(f"MusicBrainz {config}: {e}")
    total = sum(v for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"total_rows": MetadataValue.int(total), "detail": MetadataValue.json(out)})
