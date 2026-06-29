"""MusicBrainz — open music encyclopedia (artists, releases, recordings).
Uses HuggingFace datasets of MusicBrainz extracts (full Postgres dump is 10GB+)."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land MusicBrainz data → music/raw/musicbrainz/.")
def datasets_music_musicbrainz_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    candidates = [
        "jackshendriks/musicbrainz",
        "sander-wood/musicbrainz",
        "chendralegend/musicbrainz-artists",
    ]
    for candidate in candidates:
        try:
            context.log.info(f"MusicBrainz: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, "musicbrainz/musicbrainz.csv", data, "text/csv")
            context.log.info(f"MusicBrainz ({candidate}): {len(ds)} rows → {len(data):,} bytes")
            return Output({"rows": len(ds), "source": candidate}, metadata={"rows": MetadataValue.int(len(ds))})
        except Exception as e:
            context.log.warning(f"MusicBrainz {candidate}: {e}")
    context.log.warning("MusicBrainz: no public HuggingFace dataset found")
    return Output({"rows": 0}, metadata={"rows": MetadataValue.int(0)})
