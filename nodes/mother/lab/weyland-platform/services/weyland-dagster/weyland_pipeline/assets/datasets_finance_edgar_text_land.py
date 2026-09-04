"""SEC EDGAR filing TEXT — latest 10-K per company → finance/raw/filings_text/ (B113 Phase 3 — filings RAG).

Companion to the Phase-2 XBRL lander: that one lands the *structured* facts, this one lands the *narrative*. For
each company in the same ~50-mega-cap universe we read its submissions index, find the latest **10-K**, fetch
that filing's primary HTML document from EDGAR's Archives, strip it to plain text (bs4), and chunk it
SECTION-AWARE with the dagster-free ``edgar_text_parse`` helper into one tidy raw table:

  - filings_text  (cik, ticker, accn, form, filed, section, chunk_id, text)

Only the narrative sections (Business / Risk Factors / Legal Proceedings / MD&A / Market Risk) are emitted — the
numbers already live in the Phase-2 ``company_financials`` mart, so Item 8's tables would only dilute a text-RAG
corpus. Foreign filers (ASML/BABA file 20-F, not 10-K) yield no 10-K and are skipped — expected, logged.

Same SEC etiquette as the XBRL lander: descriptive ``User-Agent``, ~7 req/s, fail CLOSED — a filings_text table
with ZERO chunks raises rather than committing an empty raw layer.
"""
import io as _io
import time

import pyarrow as pa
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib.edgar_parse import select_ciks
from .datasets_lib.edgar_text_parse import chunk_filing
from .finance_common import RefreshConfig, finance_minio, finance_put_parquet, should_skip

_SEC_UA = "weyland-lab ed@timberbacklabs.com"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_PRIMARY_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{doc}"
_SEC_SLEEP = 0.15  # ~7 req/s — under SEC's ~10 req/s ceiling


def _get_json(url):
    import json
    return json.loads(_get_bytes(url))


def _get_bytes(url, retries=3, backoff=0.5):
    """GET a SEC URL → raw bytes, with the required User-Agent and a small polite retry. Fails closed."""
    import urllib.request

    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS SEC URL: {url!r}")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _SEC_UA})
            with urllib.request.urlopen(req, timeout=90) as r:  # nosec B310 — scheme asserted https; fixed SEC host
                return r.read()
        except Exception as e:  # noqa: BLE001 — retried; re-raised below if it never succeeds
            last = e
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"SEC request failed after {retries} attempts: {last}")


def _html_to_text(html_bytes):
    """Strip a filing's HTML to readable plain text — drop script/style, keep a separator so adjacent block
    text doesn't run together (the chunker then normalizes whitespace)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def _latest_10k(submissions):
    """Return (accn, primary_document, filing_date) for the most recent 10-K, or None (e.g. a 20-F foreign
    filer). ``filings.recent`` is newest-first, so the first 10-K is the latest."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form == "10-K":
            return (recent["accessionNumber"][i], recent["primaryDocument"][i], recent["filingDate"][i])
    return None


def fetch_filing_chunks(cik, ticker, company):
    """Fetch + section-chunk one company's latest 10-K. Returns [] when the company files no 10-K."""
    submissions = _get_json(_SUBMISSIONS_URL.format(cik=cik))
    latest = _latest_10k(submissions)
    if latest is None:
        return []
    accn, doc, filed = latest
    if not doc:
        return []
    time.sleep(_SEC_SLEEP)
    html = _get_bytes(_PRIMARY_DOC_URL.format(cik=cik, accn=accn.replace("-", ""), doc=doc))
    text = _html_to_text(html)
    return chunk_filing(text, cik=cik, ticker=ticker, accn=accn, form="10-K", filed=filed)


def _build_filings_text_table(rows):
    """Tidy chunk rows → the fixed filings_text silver schema (the vector fan-out reads the ``text`` column)."""
    def col(k):
        return [r[k] for r in rows]
    return pa.table({
        "cik": pa.array(col("cik"), type=pa.int64()),
        "ticker": pa.array(col("ticker"), type=pa.string()),
        "accn": pa.array(col("accn"), type=pa.string()),
        "form": pa.array(col("form"), type=pa.string()),
        "filed": pa.array(col("filed"), type=pa.string()),
        "section": pa.array(col("section"), type=pa.string()),
        "chunk_id": pa.array(col("chunk_id"), type=pa.int64()),
        "text": pa.array(col("text"), type=pa.string()),
    })


@asset(group_name="datasets_finance",
       description="Land latest-10-K narrative text (section-aware chunks) for ~50 SEC EDGAR companies → finance/raw/filings_text/.")
def datasets_finance_edgar_text_land(context, config: RefreshConfig) -> Output[dict]:
    if should_skip(context, config):  # materialize with {"force": true} to bypass the local freshness age
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})

    tickers = _get_json(_TICKERS_URL)
    time.sleep(_SEC_SLEEP)
    universe = select_ciks(tickers)   # raises (fail closed) if the ticker map came back empty
    context.log.info(f"EDGAR filings-text universe: {len(universe)} companies")

    all_rows, out = [], {}
    for cik, ticker, company in universe:
        try:
            chunks = fetch_filing_chunks(cik, ticker, company)
            all_rows.extend(chunks)
            out[ticker or str(cik)] = len(chunks)   # 0 = no 10-K (foreign filer), a valid outcome
            context.log.info(f"EDGAR text {ticker} (CIK {cik}): {len(chunks)} chunks")
            time.sleep(_SEC_SLEEP)
        except Exception as e:  # noqa: BLE001 — one bad company must not sink the rest
            out[ticker or str(cik)] = f"ERROR: {e}"
            context.log.warning(f"EDGAR text {ticker} (CIK {cik}): {e}")

    filers_ok = sum(1 for v in out.values() if isinstance(v, int) and v > 0)
    if not all_rows:
        # No company produced a single chunk — fail loudly rather than commit an empty raw layer (the
        # absent-result-as-success trap the lab's corrections warn about).
        raise RuntimeError(f"EDGAR filings-text land produced zero chunks across {len(universe)} companies: {out}")

    tbl = _build_filings_text_table(all_rows)
    buf = _io.BytesIO()
    pq.write_table(tbl, buf)
    client = finance_minio()
    finance_put_parquet(client, "filings_text/filings_text.parquet", buf.getvalue())

    context.log.info(f"landed filings_text ({tbl.num_rows:,} chunks) from {filers_ok}/{len(universe)} 10-K filers")
    return Output(out, metadata={
        "filers_with_10k": MetadataValue.int(filers_ok),
        "chunks": MetadataValue.int(tbl.num_rows),
        "detail": MetadataValue.json(out),
    })
