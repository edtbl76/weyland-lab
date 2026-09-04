"""SEC EDGAR (XBRL company facts) — ~50 curated mega-cap companies → finance/raw/ (B113 Phase 2).

For each company we fetch its full XBRL company-facts payload + its submissions metadata from the SEC HTTP
API, shape them with the dagster-free helpers in datasets_lib.edgar_parse, and land TWO tidy raw parquet tables:

  - company_financials  LONG/tidy: (cik, ticker, company, concept, unit, period_end, fy, fp, form, filed, value)
  - company_meta        dim:       (cik, ticker, company, sic, sic_description, exchange)

Like the FRED lander (and unlike the health landers), finance shapes on land — the EDGAR JSON is not a
rectangle — so raw is already tidy parquet. The broker's reader reads .parquet straight through and re-writes
silver in every format + Iceberg.

SEC requires a descriptive ``User-Agent`` on every request (weyland-lab ed@timberbacklabs.com) and rate-limits
to ~10 req/s, so we sleep a beat between calls. No API key is needed; the fetch fails CLOSED (a company we could
not fetch is logged and skipped, and a financials table with ZERO rows raises rather than committing an empty raw layer).
"""
import io as _io
import time

import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib.edgar_parse import (
    CONCEPTS,
    build_filings_table,
    build_financials_table,
    build_meta_table,
    parse_company_filings,
    parse_company_financials,
    parse_company_meta,
    select_ciks,
)
from .finance_common import RefreshConfig, finance_minio, finance_put_parquet, should_skip

_SEC_UA = "weyland-lab ed@timberbacklabs.com"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_SEC_SLEEP = 0.15  # ~7 req/s — under SEC's ~10 req/s ceiling with headroom for the two calls per company


def _get_json(url, retries=3, backoff=0.5):
    """GET a SEC endpoint → parsed JSON, with the required User-Agent and a small polite retry. Raises on the
    final failure (fail closed — a company we could not fetch must not silently vanish from the landed set)."""
    import json
    import urllib.request

    # Defence-in-depth: every URL here is built from a hardcoded https base, but assert the scheme so a future
    # refactor can never hand urlopen a file:// or custom scheme (the B310 concern).
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS SEC URL: {url!r}")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _SEC_UA})
            with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 — scheme asserted https above; fixed SEC host, no user input
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001 — retried; re-raised below if it never succeeds
            last = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"SEC request failed after {retries} attempts: {last}")


def fetch_company(cik, ticker, company):
    """Fetch (financial_rows, meta_dict, filing_rows) for one company. Pure-ish: network in, parsed data out —
    the shaping itself is delegated to the dagster-free edgar_parse helpers."""
    facts = _get_json(_FACTS_URL.format(cik=cik))
    time.sleep(_SEC_SLEEP)  # be polite between the two calls
    submissions = _get_json(_SUBMISSIONS_URL.format(cik=cik))
    rows = parse_company_financials(cik, ticker, company, facts)
    meta = parse_company_meta(cik, ticker, submissions)
    filings = parse_company_filings(cik, ticker, submissions)
    return rows, meta, filings


@asset(group_name="datasets_finance",
       description="Land ~50 SEC EDGAR companies → finance/raw/company_financials/ (tidy facts) + finance/raw/company_meta/ (dim).")
def datasets_finance_edgar_land(context, config: RefreshConfig) -> Output[dict]:
    if should_skip(context, config):  # materialize with {"force": true} to bypass the local freshness age
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})

    tickers = _get_json(_TICKERS_URL)
    time.sleep(_SEC_SLEEP)
    universe = select_ciks(tickers)   # raises (fail closed) if the ticker map came back empty
    context.log.info(f"EDGAR universe: {len(universe)} companies (first of {len(tickers)} tickers)")

    all_rows, metas, all_filings, out = [], [], [], {}
    concept_present = {label: 0 for label in CONCEPTS}
    for cik, ticker, company in universe:
        try:
            rows, meta, filings = fetch_company(cik, ticker, company)
            all_rows.extend(rows)
            metas.append(meta)
            all_filings.extend(filings)
            out[ticker or str(cik)] = len(rows)
            for label in {r["concept"] for r in rows}:
                concept_present[label] += 1
            context.log.info(f"EDGAR {ticker} (CIK {cik}): {len(rows):,} fact rows")
            time.sleep(_SEC_SLEEP)  # be polite to the API between companies (~10 req/s ceiling)
        except Exception as e:  # noqa: BLE001 — one bad company must not sink the other forty-nine
            out[ticker or str(cik)] = f"ERROR: {e}"
            context.log.warning(f"EDGAR {ticker} (CIK {cik}): {e}")

    companies_ok = sum(1 for v in out.values() if isinstance(v, int))
    if not all_rows:
        # Every company failed (or none produced a target fact) — nothing to write. Fail loudly rather than
        # commit an empty raw layer (the absent-result-as-success trap the lab's corrections warn about).
        raise RuntimeError(f"EDGAR land produced zero financial rows across {len(universe)} companies: {out}")

    client = finance_minio()

    fin = build_financials_table(all_rows)
    fin_buf = _io.BytesIO()
    pq.write_table(fin, fin_buf)
    finance_put_parquet(client, "company_financials/company_financials.parquet", fin_buf.getvalue())

    meta_tbl = build_meta_table(metas)
    meta_buf = _io.BytesIO()
    pq.write_table(meta_tbl, meta_buf)
    finance_put_parquet(client, "company_meta/company_meta.parquet", meta_buf.getvalue())

    filings_tbl = build_filings_table(all_filings)
    fil_buf = _io.BytesIO()
    pq.write_table(filings_tbl, fil_buf)
    finance_put_parquet(client, "company_filings/company_filings.parquet", fil_buf.getvalue())

    context.log.info(
        f"landed company_financials ({fin.num_rows:,} rows) + company_meta ({meta_tbl.num_rows} rows) "
        f"+ company_filings ({filings_tbl.num_rows:,} rows) from {companies_ok}/{len(universe)} companies"
    )
    return Output(out, metadata={
        "companies_ok": MetadataValue.int(companies_ok),
        "financials_rows": MetadataValue.int(fin.num_rows),
        "meta_rows": MetadataValue.int(meta_tbl.num_rows),
        "filings_rows": MetadataValue.int(filings_tbl.num_rows),
        "concept_present": MetadataValue.json(concept_present),
        "detail": MetadataValue.json(out),
    })
