"""B73 — query the datasets-lake silver formats from lakeFS with polars (Parquet / Arrow / Avro / Lance).

Reads each format of the music datasets straight from the **lakeFS S3 gateway** and runs a sample query,
proving every format is queryable from one tool. This is the **seed for the future JupyterHub notebooks**;
DuckDB (+ the pyarrow bridge) lands next as the SQL store over these same files.

Run on **rogueone** with lakeFS port-forwarded to localhost:8000 (IntelliJ k8s plugin → svc `lakefs` :8000):

    python -m venv .venv && . .venv/bin/activate
    pip install polars pylance s3fs
    export LAKEFS_ACCESS_KEY_ID=...   LAKEFS_SECRET_ACCESS_KEY=...
    python query_datasets_formats.py

The data lives at s3://<repo>/<branch>/<fmt>/<table>/ behind the gateway; polars and Lance both go through
the same Rust object_store, so they share one storage-options dict (the keys the Lance writer already uses).
"""
import io
import os

import polars as pl
import s3fs

LAKEFS_ENDPOINT = os.environ.get("LAKEFS_ENDPOINT", "http://localhost:8000")
KEY = os.environ["LAKEFS_ACCESS_KEY_ID"]
SECRET = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
REPO, BRANCH, TABLE = "music", "main", "spotify_tracks"

# object_store options → lakeFS S3 gateway (path-style, plain http). Same keys the Lance writer uses.
SO = {
    "access_key_id": KEY,
    "secret_access_key": SECRET,
    "endpoint": LAKEFS_ENDPOINT,
    "allow_http": "true",
    "region": "us-east-1",
}

# s3fs is only used to resolve the exact object name in each format's dir (dlt/transform name files by
# uuid), so the readers don't depend on glob support differing per format.
_fs = s3fs.S3FileSystem(
    key=KEY, secret=SECRET, use_ssl=False, client_kwargs={"endpoint_url": LAKEFS_ENDPOINT}
)


def _first(fmt: str, ext: str) -> str:
    base = f"{REPO}/{BRANCH}/{fmt}/{TABLE}"
    return next(f for f in _fs.ls(base) if f.endswith(ext))


def read_parquet() -> pl.DataFrame:
    return pl.read_parquet(f"s3://{_first('parquet', '.parquet')}", storage_options=SO)


def read_arrow() -> pl.DataFrame:
    # Arrow/Feather == Arrow IPC. polars `read_ipc` with storage_options routes through fsspec/s3fs (which rejects
    # the object_store keys → `AioSession … access_key_id`), so pull the bytes through s3fs like read_avro does.
    with _fs.open(_first("arrow", ".arrow"), "rb") as f:
        return pl.read_ipc(io.BytesIO(f.read()))


def read_avro() -> pl.DataFrame:
    # polars read_avro is local-only → pull the object bytes through the gateway, then parse.
    with _fs.open(_first("avro", ".avro"), "rb") as f:
        return pl.read_avro(io.BytesIO(f.read()))


def read_lance() -> pl.DataFrame:
    import lance

    # The Lance dataset is at …/lance/<table>/ directly (it contains _versions/, _transactions/, data/). Current
    # pylance's object_store only reads the S3 opts in object_store's **`aws_`-prefixed** form — the generic
    # `access_key_id` keys (which write_lance + s3fs use) are silently ignored → anonymous request → lakeFS 403.
    so = {"aws_access_key_id": KEY, "aws_secret_access_key": SECRET, "aws_endpoint": LAKEFS_ENDPOINT,
          "aws_allow_http": "true", "aws_region": "us-east-1", "aws_virtual_hosted_style_request": "false"}
    ds = lance.dataset(f"s3://{REPO}/{BRANCH}/lance/{TABLE}", storage_options=so)
    return pl.from_arrow(ds.to_table())


if __name__ == "__main__":
    for name, fn in [("parquet", read_parquet), ("arrow", read_arrow), ("avro", read_avro), ("lance", read_lance)]:
        try:
            df = fn()
            print(f"\n=== {name}: {df.height} rows x {df.width} cols ===")
            # sample query: most-danceable tracks (Spotify carries a `danceability` audio feature)
            cols = [c for c in ("track_name", "artists", "danceability") if c in df.columns]
            if "danceability" in df.columns and cols:
                print(df.select(cols).sort("danceability", descending=True).head(5))
            else:
                print(df.head(3))
        except Exception as e:  # noqa: BLE001 — per-format, so one bad reader doesn't sink the others
            print(f"\n=== {name}: FAILED -- {type(e).__name__}: {e} ===")
