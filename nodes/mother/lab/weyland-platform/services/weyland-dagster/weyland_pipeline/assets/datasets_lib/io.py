"""lakeFS / MinIO I/O — write THROUGH the lakeFS S3 gateway (versioned). The bucket is the lakeFS repo
and every key is prefixed with the branch → s3://<repo>/<branch>/<key>. Parameterized by repo so a single
implementation serves every domain (the old per-domain _common modules each hardcoded their own)."""
import io as _io
import os
import urllib.request

from minio import Minio


def endpoint() -> str:
    return os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")


def branch() -> str:
    return os.environ.get("LAKEFS_BRANCH", "main")


def client() -> Minio:
    ep = endpoint()
    return Minio(
        ep.replace("https://", "").replace("http://", ""),
        access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
        secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        secure=ep.startswith("https://"),
    )


def put(mc, repo: str, key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Put bytes at <branch>/<key> (key already includes any sub-prefix like 'parquet/…')."""
    full = f"{branch()}/{key}"
    mc.put_object(repo, full, _io.BytesIO(data), length=len(data), content_type=content_type)


def put_raw(mc, repo: str, key: str, data: bytes, content_type: str = "application/octet-stream"):
    """Put bytes under the raw/ (bronze) prefix → <branch>/raw/<key>."""
    put(mc, repo, f"raw/{key}", data, content_type)


def fput_raw(mc, repo: str, key: str, file_path: str, content_type: str = "text/csv"):
    """Upload a file from disk (streamed in parts) under raw/ — for sources too large to hold in memory."""
    mc.fput_object(repo, f"{branch()}/raw/{key}", file_path, content_type=content_type)


def fput(mc, repo: str, key: str, file_path: str, content_type: str = "application/octet-stream"):
    """Upload a file from disk (streamed in parts) at <branch>/<key> — for silver too large to hold in
    memory (key already includes any sub-prefix like 'parquet/…'). The put() variant reads the whole file
    into bytes; use this when that would OOM (the streamed open_food_facts parquet)."""
    mc.fput_object(repo, f"{branch()}/{key}", file_path, content_type=content_type)


def raw_prefix() -> str:
    return f"{branch()}/raw/"


def fetch(mc, repo: str, object_name: str) -> bytes:
    resp = mc.get_object(repo, object_name)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def download(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-datasets-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
