"""Shared helpers for health domain landing assets."""
from datetime import datetime, timedelta, timezone
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


def _last_materialized(context) -> datetime | None:
    from dagster import AssetKey
    key = AssetKey([context.asset_key.path[-1]])
    record = context.instance.get_latest_materialization_event(key)
    if record is None:
        return None
    return datetime.fromtimestamp(record.timestamp, tz=timezone.utc)


def check_source_freshness(context, url: str, max_age_days: int = 7) -> bool:
    """Two-stage freshness check. Returns True if asset should be SKIPPED (fresh), False if stale.
    Stage 1: HEAD request for Last-Modified — skip if source unchanged since last materialization.
    Stage 2: fallback to local age check if remote check fails."""
    last_mat = _last_materialized(context)
    if last_mat is None:
        return False

    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "weyland-health-land/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            last_modified_str = r.headers.get("Last-Modified")
        if last_modified_str:
            from email.utils import parsedate_to_datetime
            source_ts = parsedate_to_datetime(last_modified_str).astimezone(timezone.utc)
            if source_ts <= last_mat:
                context.log.info(f"Remote source unchanged since {last_mat.date()} — skipping")
                return True
            context.log.info(f"Remote source updated {source_ts.date()} — downloading")
            return False
    except Exception as e:
        context.log.warning(f"Remote freshness check failed ({e}) — falling back to local age check")

    age = datetime.now(tz=timezone.utc) - last_mat
    if age.days < max_age_days:
        context.log.info(f"Local age {age.days}d < {max_age_days}d — skipping")
        return True
    context.log.info(f"Local age {age.days}d >= {max_age_days}d — downloading")
    return False


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
