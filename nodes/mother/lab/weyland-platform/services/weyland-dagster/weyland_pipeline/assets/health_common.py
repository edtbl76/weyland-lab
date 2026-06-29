"""Shared helpers for health domain landing assets."""
import io
import os
import urllib.request
import zipfile

from minio import Minio

_HEALTH_REPO = "health"
_BRANCH = os.environ.get("LAKEFS_BRANCH", "main")
_ENDPOINT = os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")


def health_minio() -> Minio:
    ep = _ENDPOINT
    return Minio(
        ep.replace("https://", "").replace("http://", ""),
        access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
        secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        secure=ep.startswith("https://"),
    )


def health_put(client, key: str, data: bytes, content_type: str = "application/octet-stream"):
    full_key = f"{_BRANCH}/raw/{key}"
    client.put_object(_HEALTH_REPO, full_key, io.BytesIO(data), length=len(data), content_type=content_type)


def health_download(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-health-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def health_download_zip(client, url: str, dest_prefix: str, log, timeout: int = 1800):
    """Download a zip and put each member under dest_prefix/."""
    data = health_download(url, timeout=timeout)
    count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for fname in z.namelist():
            content = z.read(fname)
            ct = "text/csv" if fname.endswith(".csv") else "application/octet-stream"
            health_put(client, f"{dest_prefix}/{fname}", content, ct)
            log.info(f"{dest_prefix}/{fname} → {len(content):,} bytes")
            count += 1
    return count
