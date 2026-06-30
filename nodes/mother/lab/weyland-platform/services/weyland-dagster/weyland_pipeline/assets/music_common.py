"""Thin music-domain facade over datasets_lib — repo-bound convenience wrappers so the land assets keep
their existing imports (`from .music_common import music_minio, music_put, …`) while the shared mechanism
(client, put/fput, freshness) lives in datasets_lib and is maintained once for every domain."""
from .datasets_lib import io as _io
from .datasets_lib.freshness import (  # re-exported for land assets
    RefreshConfig,
    check_source_freshness,
    is_fresh_local,
    last_materialized as _last_materialized,
    should_skip,
)

_MUSIC_REPO = "music"


def music_minio():
    return _io.client()


def music_put(client, key, data, content_type="application/octet-stream"):
    _io.put_raw(client, _MUSIC_REPO, key, data, content_type)


def music_fput(client, key, file_path, content_type="text/csv"):
    _io.fput_raw(client, _MUSIC_REPO, key, file_path, content_type)


def music_download(url, timeout=600):
    return _io.download(url, timeout)
