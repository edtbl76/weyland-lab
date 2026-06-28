"""B72 step 1 — dlt EL: pull public music datasets into the MinIO `datasets/music/raw/` zone (bronze).

dlt (the design's EL tool) extracts each source and lands it via the filesystem destination to
s3://music/main/raw/<table>/ (through the lakeFS gateway, which maps to datasets/music/main/raw/).
Spotify (HuggingFace, clean single CSV) is wired first to PROVE the dlt→MinIO pipeline; FMA's
metadata CSVs have multi-row headers (a known FMA quirk) and are added next with proper parsing.

Runs in the dagster-user-code pod (already reaches external APIs). If a mesh egress policy
allow-lists hosts, HuggingFace may need adding. If a source URL 404s (datasets move), update it here.
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
    # Write THROUGH the lakeFS S3 gateway (not MinIO directly) so the raw zone is versioned: the bucket
    # is the lakeFS REPO, and dataset_name carries the BRANCH prefix (→ s3://<repo>/<branch>/raw/<table>).
    # lakeFS still stores the bytes in MinIO under datasets/music/; it adds version tracking.
    # branch goes in the bucket_url (lakeFS reads <repo>/<ref> from the path); dlt sanitizes "/" out of
    # dataset_name, so a branch there becomes ref="main_raw" (404). → s3://<repo>/<branch>.
    return filesystem(
        bucket_url=f"s3://{os.environ.get('LAKEFS_REPO', 'music')}/{os.environ.get('LAKEFS_BRANCH', 'main')}",
        credentials={
            "aws_access_key_id": os.environ["LAKEFS_ACCESS_KEY_ID"],
            "aws_secret_access_key": os.environ["LAKEFS_SECRET_ACCESS_KEY"],
            "endpoint_url": os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000"),
        },
    )


@asset(
    group_name="datasets_music",
    description="dlt EL — pull Spotify + FMA public music datasets into datasets/music/raw/ (bronze).",
)
def datasets_music_land(context) -> Output[dict]:
    os.environ["DATA_WRITER__DISABLE_COMPRESSION"] = "true"
    pipeline = dlt.pipeline(
        pipeline_name="music_datasets",
        destination=_filesystem_dest(),
        dataset_name="raw",  # branch is in bucket_url; slash-free here → s3://<repo>/<branch>/raw/<table>/
    )
    sources = [_spotify_rows()]
    for _table, (_member, _header) in _FMA_FILES.items():
        sources.append(_fma_resource(_table, _member, _header)())
    info = pipeline.run(sources, loader_file_format="csv")
    context.log.info(f"dlt load info: {info}")
    return Output(
        {"pipeline": "music_datasets", "tables": ["spotify_tracks", *_FMA_FILES], "load_info": str(info)},
        metadata={"destination": MetadataValue.text("s3://datasets/music/raw/")},
    )
