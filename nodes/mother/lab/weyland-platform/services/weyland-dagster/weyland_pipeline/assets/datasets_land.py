"""B72 step 1 — dlt EL: pull public music datasets into the MinIO `datasets/raw/` zone (bronze).

dlt (the design's EL tool) extracts each source and lands it via the filesystem destination to
s3://datasets/raw/<table>/ as CSV (loader_file_format=csv) so raw stays source-faithful. Spotify
(HuggingFace, clean single CSV) is wired first to PROVE the dlt→MinIO pipeline; FMA's metadata CSVs
have multi-row headers (a known FMA quirk) and are added next with proper parsing.

Runs in the dagster-user-code pod (already reaches external APIs). If a mesh egress policy
allow-lists hosts, HuggingFace may need adding. If a source URL 404s (datasets move), update it here.
Reuses the pod's MINIO_* creds — they must read/write the `datasets` bucket.
"""
import csv as csvmod
import io
import os
import urllib.request

import dlt
from dagster import MetadataValue, Output, asset
from dlt.destinations import filesystem

SPOTIFY_CSV_URL = (
    "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/main/dataset.csv"
)


@dlt.resource(name="spotify_tracks", write_disposition="replace")
def _spotify_rows():
    text = urllib.request.urlopen(SPOTIFY_CSV_URL, timeout=180).read().decode("utf-8", "replace")
    yield from csvmod.DictReader(io.StringIO(text))


# FMA metadata — the zip is downloaded once to /tmp and shared by all FMA resources. Its CSVs ship with
# multi-row headers (pandas multi-index), so they're read with pandas at the right header depth and the
# columns flattened to single names. genres.csv is flat; tracks/echonest are multi-level. features.csv
# (~1 GB) is intentionally skipped. <table> -> (zip member, pandas header rows).
FMA_METADATA_URL = "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip"
_FMA_ZIP = "/tmp/fma_metadata.zip"
_FMA_FILES = {
    "fma_tracks": ("tracks.csv", [0, 1]),
    "fma_genres": ("genres.csv", 0),
    "fma_echonest": ("echonest.csv", [0, 1, 2]),
}


def _fma_records(member, header):
    import zipfile
    import numpy as np
    import pandas as pd

    if not os.path.exists(_FMA_ZIP):
        urllib.request.urlretrieve(FMA_METADATA_URL, _FMA_ZIP)  # ~342 MB, once
    with zipfile.ZipFile(_FMA_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith(member))
        with z.open(name) as f:
            df = pd.read_csv(f, index_col=0, header=header, low_memory=False)
    if hasattr(df.columns, "levels"):  # flatten MultiIndex columns to single names
        df.columns = [
            "_".join(str(x) for x in col if str(x) and not str(x).startswith("Unnamed"))
            for col in df.columns
        ]
    df = df.reset_index().replace({np.nan: None})
    return df.to_dict("records")


def _fma_resource(table_name, member, header):
    @dlt.resource(name=table_name, write_disposition="replace")
    def _rows():
        yield from _fma_records(member, header)

    return _rows


def _filesystem_dest():
    return filesystem(
        bucket_url=os.environ.get("DATASETS_BUCKET_URL", "s3://datasets"),
        credentials={
            "aws_access_key_id": os.environ["MINIO_ACCESS_KEY"],
            "aws_secret_access_key": os.environ["MINIO_SECRET_KEY"],
            "endpoint_url": os.environ.get(
                "MINIO_ENDPOINT_URL", "http://minio.minio.svc.cluster.local:9000"
            ),
        },
    )


@asset(
    group_name="datasets",
    description="dlt EL — pull Spotify + FMA public music datasets into MinIO datasets/raw/ (bronze).",
)
def datasets_land(context) -> Output[dict]:
    # dlt gzips loader files by default → keep raw source-faithful + downstream-friendly (plain .csv,
    # matches the s3 source *.csv path_spec and the pyarrow transform).
    os.environ["DATA_WRITER__DISABLE_COMPRESSION"] = "true"
    pipeline = dlt.pipeline(
        pipeline_name="music_datasets",
        destination=_filesystem_dest(),
        dataset_name="raw",  # → s3://datasets/raw/<table>/
    )
    sources = [_spotify_rows()]
    for _table, (_member, _header) in _FMA_FILES.items():
        sources.append(_fma_resource(_table, _member, _header)())
    info = pipeline.run(sources, loader_file_format="csv")
    context.log.info(f"dlt load info: {info}")
    return Output(
        {"pipeline": "music_datasets", "tables": ["spotify_tracks", *_FMA_FILES], "load_info": str(info)},
        metadata={"destination": MetadataValue.text("s3://datasets/raw/")},
    )
