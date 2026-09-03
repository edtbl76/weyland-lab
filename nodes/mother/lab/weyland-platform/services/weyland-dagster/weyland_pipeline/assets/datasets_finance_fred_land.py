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
"""
import io as _io
import os
import time

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib.fred_parse import (
    SERIES_IDS,
    build_macro_table,
    build_meta_table,
    extract_series_meta,
    observations_to_rows,
)
from .finance_common import RefreshConfig, finance_minio, finance_put_parquet, should_skip

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


@asset(group_name="datasets_finance",
       description="Land 13 FRED macro series → finance/raw/fred_macro/ (tidy) + finance/raw/fred_series_meta/ (dim).")
def datasets_finance_fred_land(context, config: RefreshConfig) -> Output[dict]:
    if should_skip(context, config):  # materialize with {"force": true} to bypass the local freshness age
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        # Fail closed — a missing key must be a loud error, not an empty-but-"successful" land.
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

    ok = sum(1 for v in out.values() if isinstance(v, int))
    if not all_rows:
        # Every series failed — nothing to write. Fail loudly rather than commit an empty raw layer.
        raise RuntimeError(f"FRED land produced zero observations across {len(SERIES_IDS)} series: {out}")

    client = finance_minio()

    macro = build_macro_table(all_rows)
    macro_buf = _io.BytesIO()
    pq.write_table(macro, macro_buf)
    finance_put_parquet(client, "fred_macro/fred_macro.parquet", macro_buf.getvalue())

    meta_tbl = build_meta_table(metas)
    meta_buf = _io.BytesIO()
    pq.write_table(meta_tbl, meta_buf)
    finance_put_parquet(client, "fred_series_meta/fred_series_meta.parquet", meta_buf.getvalue())

    context.log.info(
        f"landed fred_macro ({macro.num_rows:,} rows) + fred_series_meta ({meta_tbl.num_rows} rows) "
        f"from {ok}/{len(SERIES_IDS)} series"
    )
    return Output(out, metadata={
        "series_ok": MetadataValue.int(ok),
        "macro_rows": MetadataValue.int(macro.num_rows),
        "meta_rows": MetadataValue.int(meta_tbl.num_rows),
        "detail": MetadataValue.json(out),
    })
