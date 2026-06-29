"""FMA (Free Music Archive) metadata — tracks, genres, echonest audio features.
Multi-row header CSVs read via pandas; zip cached at /tmp to avoid re-download."""
import io
import os
import urllib.request
import zipfile

import numpy as np
import pandas as pd

from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put

FMA_METADATA_URL = "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip"
_FMA_ZIP = "/tmp/fma_metadata.zip"
_FMA_FILES = {
    "fma_tracks":   ("tracks.csv",   [0, 1]),
    "fma_genres":   ("genres.csv",   0),
    "fma_echonest": ("echonest.csv", [0, 1, 2]),
}


def _fma_records(member, header):
    if not os.path.exists(_FMA_ZIP):
        urllib.request.urlretrieve(FMA_METADATA_URL, _FMA_ZIP)
    with zipfile.ZipFile(_FMA_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith(member))
        with z.open(name) as f:
            df = pd.read_csv(f, index_col=0, header=header, low_memory=False)
    if hasattr(df.columns, "levels"):
        df.columns = [
            "_".join(str(x) for x in col if str(x) and not str(x).startswith("Unnamed"))
            for col in df.columns
        ]
    return df.reset_index().replace({np.nan: None})


@asset(group_name="datasets_music", description="Land FMA tracks CSV → music/raw/fma_tracks/.")
def datasets_music_fma_tracks_land(context) -> Output[dict]:
    client = music_minio()
    context.log.info("FMA Tracks: downloading")
    df = _fma_records("tracks.csv", [0, 1])
    data = df.to_csv(index=False).encode("utf-8")
    music_put(client, "fma_tracks/fma_tracks.csv", data, "text/csv")
    context.log.info(f"fma_tracks/fma_tracks.csv → {len(data):,} bytes")
    return Output({"rows": len(df), "bytes": len(data)}, metadata={"rows": MetadataValue.int(len(df))})


@asset(group_name="datasets_music", description="Land FMA genres CSV → music/raw/fma_genres/.")
def datasets_music_fma_genres_land(context) -> Output[dict]:
    client = music_minio()
    context.log.info("FMA Genres: downloading")
    df = _fma_records("genres.csv", 0)
    data = df.to_csv(index=False).encode("utf-8")
    music_put(client, "fma_genres/fma_genres.csv", data, "text/csv")
    context.log.info(f"fma_genres/fma_genres.csv → {len(data):,} bytes")
    return Output({"rows": len(df), "bytes": len(data)}, metadata={"rows": MetadataValue.int(len(df))})


@asset(group_name="datasets_music", description="Land FMA echonest audio features CSV → music/raw/fma_echonest/.")
def datasets_music_fma_echonest_land(context) -> Output[dict]:
    client = music_minio()
    context.log.info("FMA Echonest: downloading")
    df = _fma_records("echonest.csv", [0, 1, 2])
    data = df.to_csv(index=False).encode("utf-8")
    music_put(client, "fma_echonest/fma_echonest.csv", data, "text/csv")
    context.log.info(f"fma_echonest/fma_echonest.csv → {len(data):,} bytes")
    return Output({"rows": len(df), "bytes": len(data)}, metadata={"rows": MetadataValue.int(len(df))})
