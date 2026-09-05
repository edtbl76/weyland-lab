"""FRED (Federal Reserve Economic Data, St. Louis Fed) — 13 macro series → finance/raw/ (B113 Phase 1).

For each series we fetch the series metadata + its full observation history from the FRED HTTP API, shape
them with the dagster-free helpers in datasets_lib.fred_parse, and land TWO tidy raw parquet tables:

  - fred_macro        LONG/tidy: (series_id, date, value)   — all 13 series stacked
  - fred_series_meta  dim:       (series_id, title, units, frequency, seasonal_adjustment)

Unlike the health landers (which persist the source's own JSON/CSV/XPT as raw and let the broker shape it),
finance shapes on land — the FRED JSON is not a rectangle — so raw is already tidy parquet. The broker's
reader reads .parquet straight through and re-writes silver in every format + Iceberg.

FRED_API_KEY comes from the environment (gitignored scripts/.env → sealed Secret in-cluster); it is NEVER
logged (it rides in the query string, so only the series id is ever logged) and NEVER committed.

B158 follow-up B: the land scaffold (skip / fail-closed / minio / parquet write / Output) is now generated
by ``datasets_lib.landers.build_land_asset``; this file carries only the FRED-specific fetch + the
``_produce`` that shapes the two tables.
"""
import os
import time

from .datasets_lib.fred_parse import (
    SERIES_IDS,
    build_macro_table,
    build_meta_table,
    extract_series_meta,
    observations_to_rows,
)
from .datasets_lib.landers import build_land_asset

_FRED_BASE = "https://api.stlouisfed.org/fred"


def _get_json(url, retries=3, backoff=0.5):
    """GET a FRED endpoint → parsed JSON, with a small polite retry. Raises on the final failure (fail
    closed — a series we could not fetch must not silently vanish from the landed set)."""
    import json
    import urllib.request

    # Defence-in-depth: every URL here is built from the hardcoded https _FRED_BASE, but assert the scheme
    # so a future refactor can never hand urlopen a file:// or custom scheme (the B310 concern).
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS FRED URL: {url!r}")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "weyland-datasets-land/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 — scheme asserted https above; fixed FRED host, no user input
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001 — retried; re-raised below if it never succeeds
            last = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"FRED request failed after {retries} attempts: {last}")


def fetch_series(series_id, api_key):
    """Fetch (metadata_dict, observation_rows) for one series. Pure-ish: network in, parsed data out —
    the shaping itself is delegated to the dagster-free fred_parse helpers."""
    meta_url = f"{_FRED_BASE}/series?series_id={series_id}&api_key={api_key}&file_type=json"
    obs_url = f"{_FRED_BASE}/series/observations?series_id={series_id}&api_key={api_key}&file_type=json"
    meta = extract_series_meta(_get_json(meta_url))
    rows = observations_to_rows(series_id, _get_json(obs_url))
    return meta, rows


def _produce(context):
    """Fetch every series → the two tidy tables + a per-series detail dict. A missing API key fails loud;
    one bad series is logged and skipped (fail-closed on the whole set is the factory's zero-rows guard)."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY is not set in the environment (expected from the sealed Secret / scripts/.env)")

    all_rows, metas, out = [], [], {}
    for sid in SERIES_IDS:
        try:
            meta, rows = fetch_series(sid, api_key)
            all_rows.extend(rows)
            metas.append(meta)
            out[sid] = len(rows)
            context.log.info(f"FRED {sid}: {len(rows):,} observations")
            time.sleep(0.2)  # be polite to the API between series (FRED is generous, but don't hammer)
        except Exception as e:  # noqa: BLE001 — one bad series must not sink the other twelve
            out[sid] = f"ERROR: {e}"
            context.log.warning(f"FRED {sid}: {e}")

    tables = {} if not all_rows else {
        "fred_macro": build_macro_table(all_rows),
        "fred_series_meta": build_meta_table(metas),
    }
    return tables, out


datasets_finance_fred_land = build_land_asset(
    "datasets_finance_fred_land", "finance", _produce,
    group="datasets_finance",
    description="Land 13 FRED macro series → finance/raw/fred_macro/ (tidy) + finance/raw/fred_series_meta/ (dim).",
)
