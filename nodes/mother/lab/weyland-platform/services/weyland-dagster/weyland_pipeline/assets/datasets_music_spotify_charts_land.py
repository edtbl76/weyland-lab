"""Spotify Charts — weekly top charts by country from HuggingFace."""
import io
import csv as csvmod
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put


@asset(group_name="datasets_music", description="Land Spotify Charts data → music/raw/spotify_charts/.")
def datasets_music_spotify_charts_land(context) -> Output[dict]:
    from datasets import load_dataset
    client = music_minio()
    candidates = [
        "luisgasco/spotify-charts",
        "MicPie/unpacked_spotify_charts_weekly_global_top_200_2017-2021",
        "leobeeson/spotify_global_top_charts",
    ]
    for candidate in candidates:
        try:
            context.log.info(f"Spotify Charts: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            music_put(client, "spotify_charts/spotify_charts.csv", data, "text/csv")
            context.log.info(f"Spotify Charts ({candidate}): {len(ds)} rows → {len(data):,} bytes")
            return Output({"rows": len(ds), "source": candidate}, metadata={"rows": MetadataValue.int(len(ds))})
        except Exception as e:
            context.log.warning(f"Spotify Charts {candidate}: {e}")
    context.log.warning("Spotify Charts: no public HuggingFace dataset found")
    return Output({"rows": 0}, metadata={"rows": MetadataValue.int(0)})
