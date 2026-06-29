"""Spotify tracks dataset — HuggingFace CSV download."""
import csv as csvmod
import io
import urllib.request

from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put, music_download, check_source_freshness

SPOTIFY_CSV_URL = (
    "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv"
)


@asset(group_name="datasets_music", description="Land Spotify tracks CSV → music/raw/spotify_tracks/.")
def datasets_music_spotify_land(context) -> Output[dict]:
    if check_source_freshness(context, SPOTIFY_CSV_URL):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    client = music_minio()
    context.log.info("Spotify: downloading CSV")
    data = music_download(SPOTIFY_CSV_URL, timeout=180)
    music_put(client, "spotify_tracks/spotify_tracks.csv", data, "text/csv")
    context.log.info(f"spotify_tracks/spotify_tracks.csv → {len(data):,} bytes")
    return Output({"bytes": len(data)}, metadata={"bytes": MetadataValue.int(len(data))})
