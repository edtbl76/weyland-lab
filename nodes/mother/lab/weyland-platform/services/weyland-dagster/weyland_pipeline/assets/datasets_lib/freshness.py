"""Freshness — in-asset differential downloads. A land asset checks its own last materialization and
skips the download if the source is unchanged, so a daily schedule (or manual run) only re-fetches stale
sources. RefreshConfig.force bypasses the skip from the launchpad — a non-destructive replacement for the
'wipe materializations' hack we needed twice tonight (nhanes, musicbrainz) just to force a re-download."""
from datetime import datetime, timezone

import dagster as dg

from . import io


class RefreshConfig(dg.Config):
    """Materialize with {"force": true} in the launchpad to bypass the freshness skip and re-download."""
    force: bool = False


def last_materialized(context):
    """UTC datetime of this asset's last materialization, or None."""
    key = dg.AssetKey([context.asset_key.path[-1]])
    record = context.instance.get_latest_materialization_event(key)
    if record is None:
        return None
    return datetime.fromtimestamp(record.timestamp, tz=timezone.utc)


def check_source_freshness(context, url: str, max_age_days: int = 30) -> bool:
    """Two-stage. (1) Remote: HEAD for Last-Modified → skip if source unchanged since last materialization.
    (2) Local fallback if the HEAD fails/has no header: skip if materialized within max_age_days.
    Returns True = SKIP (fresh), False = download."""
    last_mat = last_materialized(context)
    if last_mat is None:
        return False
    try:
        import urllib.request

        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "weyland-datasets-land/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            last_modified_str = r.headers.get("Last-Modified")
        if last_modified_str:
            from email.utils import parsedate_to_datetime

            source_ts = parsedate_to_datetime(last_modified_str).astimezone(timezone.utc)
            if source_ts <= last_mat:
                context.log.info(f"Remote source unchanged since {last_mat.date()} — skipping download")
                return True
            context.log.info(f"Remote source updated {source_ts.date()} > last mat {last_mat.date()} — downloading")
            return False
    except Exception as e:  # noqa: BLE001 — remote check is best-effort; fall through to local age
        context.log.warning(f"Remote freshness check failed ({e}) — falling back to local age check")

    age = datetime.now(tz=timezone.utc) - last_mat
    if age.days < max_age_days:
        context.log.info(f"Local age {age.days}d < {max_age_days}d — skipping download")
        return True
    context.log.info(f"Local age {age.days}d >= {max_age_days}d — downloading")
    return False


def is_fresh_local(context, max_age_days: int = 30) -> bool:
    """Local-only freshness (HuggingFace sources have no URL to HEAD). True = SKIP."""
    last_mat = last_materialized(context)
    if last_mat is None:
        return False
    age = datetime.now(tz=timezone.utc) - last_mat
    if age.days < max_age_days:
        context.log.info(f"Fresh ({age.days}d < {max_age_days}d) — skipping download")
        return True
    context.log.info(f"Stale ({age.days}d >= {max_age_days}d) — downloading")
    return False


def should_skip(context, config: RefreshConfig, *, url: str = None, max_age_days: int = 30) -> bool:
    """Unified gate for land assets: force overrides everything, else the appropriate freshness check.
    Returns True = SKIP the download."""
    if config.force:
        context.log.info("force=True — bypassing freshness, re-downloading")
        return False
    if url:
        return check_source_freshness(context, url, max_age_days)
    return is_fresh_local(context, max_age_days)
