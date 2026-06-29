"""Shared helpers for music domain landing assets."""
import io
import os
import urllib.request
import zipfile

from minio import Minio

_MUSIC_REPO = os.environ.get("LAKEFS_REPO", "music")
_BRANCH = os.environ.get("LAKEFS_BRANCH", "main")
_ENDPOINT = os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")


def music_minio() -> Minio:
    ep = _ENDPOINT
    return Minio(
        ep.replace("https://", "").replace("http://", ""),
        access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
        secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        secure=ep.startswith("https://"),
    )


def music_put(client, key: str, data: bytes, content_type: str = "application/octet-stream"):
    full_key = f"{_BRANCH}/raw/{key}"
    client.put_object(_MUSIC_REPO, full_key, io.BytesIO(data), length=len(data), content_type=content_type)


def music_download(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-music-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
