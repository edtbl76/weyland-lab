"""Shared helpers for music domain landing assets."""
from datetime import datetime, timedelta, timezone
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


def _last_materialized(context) -> datetime | None:
    """Return the UTC datetime of the last materialization, or None."""
    from dagster import AssetKey
    key = AssetKey([context.asset_key.path[-1]])
    record = context.instance.get_latest_materialization_event(key)
    if record is None:
        return None
    return datetime.fromtimestamp(record.timestamp, tz=timezone.utc)


def check_source_freshness(context, url: str, max_age_days: int = 30) -> bool:
    """Two-stage freshness check:
    1. Remote: HEAD request for Last-Modified → skip if source unchanged since last materialization.
    2. Local fallback: if remote check fails/missing, skip if materialized within max_age_days.
    Returns True if the asset should be SKIPPED (data is fresh), False if it should download."""
    last_mat = _last_materialized(context)
    if last_mat is None:
        return False  # never materialized → must download

    # Stage 1: remote Last-Modified check
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "weyland-music-land/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            last_modified_str = r.headers.get("Last-Modified")
        if last_modified_str:
            from email.utils import parsedate_to_datetime
            source_ts = parsedate_to_datetime(last_modified_str).astimezone(timezone.utc)
            if source_ts <= last_mat:
                context.log.info(f"Remote source unchanged since {last_mat.date()} — skipping download")
                return True  # fresh
            context.log.info(f"Remote source updated {source_ts.date()} after last materialization {last_mat.date()} — downloading")
            return False  # stale
    except Exception as e:
        context.log.warning(f"Remote freshness check failed ({e}) — falling back to local age check")

    # Stage 2: local age fallback
    age = datetime.now(tz=timezone.utc) - last_mat
    if age.days < max_age_days:
        context.log.info(f"Local age {age.days}d < {max_age_days}d — skipping download")
        return True
    context.log.info(f"Local age {age.days}d >= {max_age_days}d — downloading")
    return False


def is_fresh_local(context, max_age_days: int = 30) -> bool:
    """Local-only freshness check for HuggingFace assets (no remote URL to HEAD).
    Returns True if asset should be SKIPPED (materialized within max_age_days)."""
    last_mat = _last_materialized(context)
    if last_mat is None:
        return False
    age = datetime.now(tz=timezone.utc) - last_mat
    if age.days < max_age_days:
        context.log.info(f"Fresh ({age.days}d < {max_age_days}d) — skipping download")
        return True
    context.log.info(f"Stale ({age.days}d >= {max_age_days}d) — downloading")
    return False


def music_download(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-music-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
