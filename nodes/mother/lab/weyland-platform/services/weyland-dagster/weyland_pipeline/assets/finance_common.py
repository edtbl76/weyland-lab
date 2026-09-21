"""Thin finance-domain facade over datasets_lib — repo-bound wrappers so the finance land assets keep
tidy imports while the shared mechanism lives in datasets_lib. Mirrors health_common.py; the only finance
specifics are the repo name and the raw-parquet put helper (finance lands already-shaped tidy parquet, not
the source's own JSON — unlike health, which lands raw JSON/CSV/XPT)."""
from .datasets_lib import io as _io
# minio/download carry NO finance specialization — they are pure pass-throughs, so re-export them rather
# than re-declaring identical bodies here and in every sibling *_common.py (B162: shallow/over-split). The
# functions below ARE the real facade — they bind the finance repo, which is genuine domain value.
from .datasets_lib.io import client as finance_minio, download as finance_download
from .datasets_lib.freshness import (  # re-exported for land assets
    RefreshConfig,
    check_source_freshness,
    is_fresh_local,
    should_skip,
)

_FINANCE_REPO = "finance"


def finance_put(client, key, data, content_type="application/octet-stream"):
    """Put bytes under finance/raw/<key>."""
    _io.put_raw(client, _FINANCE_REPO, key, data, content_type)


def finance_put_parquet(client, key, data):
    """Put a serialized parquet blob under finance/raw/<key> (content-type set for catalog/browsers)."""
    _io.put_raw(client, _FINANCE_REPO, key, data, "application/vnd.apache.parquet")
