"""Thin health-domain facade over datasets_lib — repo-bound wrappers so the land assets keep their
existing imports while the shared mechanism lives in datasets_lib. health_download_zip is health-specific
(several sources arrive as zips of CSVs) so it stays here, built on the shared download + put."""
import io as _stdio
import zipfile

from .datasets_lib import io as _io
from .datasets_lib.freshness import (  # re-exported for land assets
    RefreshConfig,
    check_source_freshness,
    is_fresh_local,
    last_materialized as _last_materialized,
    should_skip,
)

_HEALTH_REPO = "health"


def health_minio():
    return _io.client()


def health_put(client, key, data, content_type="application/octet-stream"):
    _io.put_raw(client, _HEALTH_REPO, key, data, content_type)


def health_fput(client, key, file_path, content_type="text/csv"):
    _io.fput_raw(client, _HEALTH_REPO, key, file_path, content_type)


def health_download(url, timeout=600):
    return _io.download(url, timeout)


def health_download_zip(client, url, dest_prefix, log, timeout=1800):
    """Download a zip and put each member under dest_prefix/ (raw/)."""
    data = _io.download(url, timeout=timeout)
    count = 0
    with zipfile.ZipFile(_stdio.BytesIO(data)) as z:
        for fname in z.namelist():
            content = z.read(fname)
            ct = "text/csv" if fname.endswith(".csv") else "application/octet-stream"
            health_put(client, f"{dest_prefix}/{fname}", content, ct)
            log.info(f"{dest_prefix}/{fname} → {len(content):,} bytes")
            count += 1
    return count
