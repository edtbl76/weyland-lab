"""Thin music-domain facade over datasets_lib — repo-bound convenience wrappers so the land assets keep
their existing imports (`from .music_common import music_minio, music_put, …`) while the shared mechanism
(client, put/fput, freshness) lives in datasets_lib and is maintained once for every domain."""
from .datasets_lib import io as _io
# minio/download carry no music specialization → re-export, don't re-declare (B162: shallow/over-split).
from .datasets_lib.io import client as music_minio, download as music_download
from .datasets_lib.freshness import (  # re-exported for land assets
    RefreshConfig,
    check_source_freshness,
    is_fresh_local,
    last_materialized as _last_materialized,
    should_skip,
)

_MUSIC_REPO = "music"


def music_put(client, key, data, content_type="application/octet-stream"):
    _io.put_raw(client, _MUSIC_REPO, key, data, content_type)


def music_fput(client, key, file_path, content_type="text/csv"):
    _io.fput_raw(client, _MUSIC_REPO, key, file_path, content_type)
