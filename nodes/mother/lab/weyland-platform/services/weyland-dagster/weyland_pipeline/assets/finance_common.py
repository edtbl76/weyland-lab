"""Thin finance-domain facade over datasets_lib — repo-bound wrappers so the finance land assets keep
tidy imports while the shared mechanism lives in datasets_lib. Mirrors health_common.py; the only finance
specifics are the repo name and the raw-parquet put helper (finance lands already-shaped tidy parquet, not
the source's own JSON — unlike health, which lands raw JSON/CSV/XPT)."""
from .datasets_lib import io as _io
from .datasets_lib.freshness import (  # re-exported for land assets
    RefreshConfig,
    check_source_freshness,
    is_fresh_local,
    should_skip,
)

_FINANCE_REPO = "finance"


def finance_minio():
    return _io.client()


def finance_put(client, key, data, content_type="application/octet-stream"):
    """Put bytes under finance/raw/<key>."""
    _io.put_raw(client, _FINANCE_REPO, key, data, content_type)


def finance_put_parquet(client, key, data):
    """Put a serialized parquet blob under finance/raw/<key> (content-type set for catalog/browsers)."""
    _io.put_raw(client, _FINANCE_REPO, key, data, "application/vnd.apache.parquet")


def finance_download(url, timeout=600):
    return _io.download(url, timeout)
