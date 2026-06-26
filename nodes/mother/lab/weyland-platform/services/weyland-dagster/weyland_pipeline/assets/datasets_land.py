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
    description="dlt EL — pull public music datasets into MinIO datasets/raw/ (bronze). Spotify wired; FMA next.",
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
    info = pipeline.run(_spotify_rows(), loader_file_format="csv")
    context.log.info(f"dlt load info: {info}")
    return Output(
        {"pipeline": "music_datasets", "load_info": str(info)},
        metadata={"destination": MetadataValue.text("s3://datasets/raw/")},
    )
