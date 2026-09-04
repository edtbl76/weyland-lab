"""Dagster-free SEC EDGAR (XBRL) parse + shape helpers for the finance domain (B113 Phase 2).

Deliberately self-contained: ONLY absolute imports, NO ``from . import ...`` and NO dagster — the same
rule ``fred_parse.py`` follows so the test lane can load this module in isolation (conftest's
``load_isolated``) with just pyarrow, never the dagster runtime. The land asset in
``datasets_finance_edgar_land.py`` does the network fetch and hands the raw JSON to these pure functions;
the finance ``DomainConfig`` in ``datasets_finance_transform.py`` imports the allowlist constants below and
UNIONS them with the Phase-1 FRED ones so the config's knobs and the silver schema stay in one grep-able,
unit-testable place.

SEC EDGAR API shapes (confirmed live 2026-09-03):
  - ticker→CIK map:   https://www.sec.gov/files/company_tickers.json → {"0": {cik_str:int, ticker, title}, ...}
  - company facts:    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json
                        → facts["us-gaap"][Concept]["units"][unit] = [{end, val, fy, fp, form, filed, accn, frame?}]
  - submissions:      https://data.sec.gov/submissions/CIK{cik:010d}.json
                        → {cik, name, sic, sicDescription, tickers:[...], exchanges:[...], ...}

Two tidy raw tables are produced, mirroring FRED's (fred_macro, fred_series_meta):
  - company_financials  LONG/tidy fact rows: (cik, ticker, company, concept, unit, period_end, fy, fp, form, filed, value)
  - company_meta         dim:                (cik, ticker, company, sic, sic_description, exchange)

Load-bearing gotchas mirrored from FRED: a value can arrive missing (None / literal ``"."``) — ``parse_edgar_value``
maps those to ``None`` and everything else to ``float`` rather than raising; and a concept a company never
reported is simply absent from ``facts["us-gaap"]`` — we SKIP it (never crash), the same fail-soft posture as
one bad FRED cell. Revenue has a fallback: newer filers report ``RevenueFromContractWithCustomerExcludingAssessedTax``
instead of the older ``Revenues`` concept, so the ``revenue`` label tries them in order.
"""
from datetime import date, datetime

import pyarrow as pa

# --- finance domain declarative knobs (imported by datasets_finance_transform.py's DomainConfig) --------
# The curated company universe: the FIRST 50 tickers in SEC's company_tickers.json, which is ordered by a
# popularity/size index (mega-caps: NVDA, AAPL, GOOGL, MSFT, AMZN, …). Stable so the stacked table is deterministic.
CIK_COUNT = 50

# Target us-gaap concepts, mapped to a clean snake label. Each label lists its raw XBRL concept name(s) in
# Each label maps to a tuple of us-gaap concept names that are all UNIONED under it (deduped per period).
# ``revenue`` needs two: newer filers report RevenueFromContractWithCustomerExcludingAssessedTax while older
# periods use Revenues, and a single filer spans both (Apple's Revenues stops at 2018) — so both are kept, not
# just the first present. Order is stable so the stacked company_financials table is deterministic.
CONCEPTS = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
    "eps_basic": ("EarningsPerShareBasic",),
    "shares_outstanding": ("CommonStockSharesOutstanding",),
}

# Only annual + quarterly filings — the two forms the fact rows are restricted to.
TARGET_FORMS = ("10-K", "10-Q")

# raw/ folder names the broker fans out (table per folder). Single-file folders.
COMPANY_FINANCIALS = "company_financials"
COMPANY_META = "company_meta"
COMPANY_FILINGS = "company_filings"   # Phase 2 graph: the 10-K/10-Q filing history feeding the Neo4j graph
EDGAR_TABLES = ("company_financials", "company_meta", "company_filings")
EDGAR_RAW_TABLES = frozenset({COMPANY_FINANCIALS, COMPANY_META, COMPANY_FILINGS})

# ClickHouse (Phase 2): the two analytical tables — native s3() ingest of the silver parquet. company_filings
# is graph data (→ Neo4j), not OLAP, so it stays out of ClickHouse.
EDGAR_CLICKHOUSE_ALLOW = frozenset({COMPANY_FINANCIALS, COMPANY_META})

# Iceberg gold (Phase 2): all three — the mart reads financials+meta; filings is catalogued + read by the graph.
EDGAR_ICEBERG_ALLOW = frozenset({COMPANY_FINANCIALS, COMPANY_META, COMPANY_FILINGS})

# The explicit silver schemas — the code is the source of truth for what the broker writes.
FINANCIALS_COLUMNS = (
    "cik", "ticker", "company", "concept", "unit", "period_end", "fy", "fp", "form", "filed", "value",
)
META_COLUMNS = ("cik", "ticker", "company", "sic", "sic_description", "exchange")


def parse_edgar_value(v):
    """One XBRL fact value → float or None.

    EDGAR values are usually already numeric, but coerce defensively: None, blank / whitespace-only, and the
    literal ``"."`` (the FRED-style missing sentinel) all map to None; a value that is neither a sentinel nor a
    parseable number is returned as None (rather than raising) so one bad fact cannot sink a company —
    the land asset counts nulls, so a wholesale-null concept is still visible downstream.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "" or s == ".":
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_edgar_date(v):
    """An EDGAR date string (``YYYY-MM-DD``) → a ``datetime.date``, or None if unparseable/empty."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _to_int(v):
    """A best-effort int (XBRL ``fy``) → int or None; never raises on junk."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _filed_sort_key(d):
    """Sort key for the dedup-by-latest-filed compare — a missing filed date sorts oldest."""
    return d if isinstance(d, date) else date.min


def select_ciks(tickers_json):
    """Pick the curated company universe from SEC's company_tickers.json.

    Accepts the raw object ({"0": {cik_str, ticker, title}, ...}) or a list of those entry dicts. Returns the
    FIRST ``CIK_COUNT`` entries as ``[(cik:int, ticker:str, title:str), ...]``, ordered by the numeric index key
    (the source's size/popularity order) so the selection is deterministic. Raises ValueError on an empty payload
    (a ticker map that returned nothing is a real failure, not an empty-but-fine result — fail closed).
    """
    if isinstance(tickers_json, dict):
        # keyed by a stringified index ("0","1",…) — order by the integer key, not dict insertion order.
        try:
            keys = sorted(tickers_json, key=lambda k: int(k))
        except (TypeError, ValueError):
            keys = list(tickers_json)
        entries = [tickers_json[k] for k in keys]
    else:
        entries = list(tickers_json or [])
    if not entries:
        raise ValueError("SEC company_tickers.json carried no entries")
    out = []
    for e in entries[:CIK_COUNT]:
        cik = e.get("cik_str")
        if cik is None:
            continue
        out.append((int(cik), e.get("ticker"), e.get("title")))
    return out


def parse_company_financials(cik, ticker, company, facts_json):
    """Shape one company's XBRL facts into tidy/long fact rows for the target concepts.

    Returns [{cik, ticker, company, concept (clean label), unit, period_end (date), fy, fp, form, filed (date),
    value (float|None)}, ...]. Only forms in ``TARGET_FORMS`` (10-K / 10-Q) are kept; rows with an unparseable
    ``period_end`` are dropped (a fact keyed on the period must have one). A label UNIONS all of its
    raw concept names (so ``revenue`` picks up both the old ``Revenues`` and the newer contract-revenue concept
    across the periods each covers); a concept a company never reported is simply absent and SKIPPED — never a
    crash. Deduped to the LATEST-``filed`` row per (cik, concept, period_end, form) so a restated fact does not
    double-count and any period reported under two raw concepts collapses to one.
    """
    facts = ((facts_json or {}).get("facts") or {}).get("us-gaap") or {}
    best = {}
    for label, raw_concepts in CONCEPTS.items():
        # Union ALL present raw concepts under this label — NOT first-present-wins. A filer reports the OLD
        # `Revenues` for pre-2018 periods and the NEWER `RevenueFromContractWithCustomerExcludingAssessedTax`
        # for recent ones, so breaking on the first present concept silently drops the recent revenue (Apple's
        # `Revenues` stops at 2018). The dedup by (cik, label, period_end, form) below collapses any period a
        # filer happened to report under both concepts.
        for raw in raw_concepts:
            concept_obj = facts.get(raw)
            if concept_obj is None:
                continue  # this company never reported this concept — skip, do not crash
            units = concept_obj.get("units") or {}
            for unit, entries in units.items():
                for e in entries or []:
                    form = e.get("form")
                    if form not in TARGET_FORMS:
                        continue
                    period_end = parse_edgar_date(e.get("end"))
                    if period_end is None:
                        continue
                    filed = parse_edgar_date(e.get("filed"))
                    row = {
                        "cik": cik,
                        "ticker": ticker,
                        "company": company,
                        "concept": label,
                        "unit": unit,
                        "period_end": period_end,
                        "fy": _to_int(e.get("fy")),
                        "fp": e.get("fp"),
                        "form": form,
                        "filed": filed,
                        "value": parse_edgar_value(e.get("val")),
                    }
                    key = (cik, label, period_end, form)
                    prev = best.get(key)
                    if prev is None or _filed_sort_key(filed) >= _filed_sort_key(prev["filed"]):
                        best[key] = row
    return list(best.values())


def parse_company_meta(cik, ticker, submissions_json):
    """Pull the finance dim fields from a company's submissions payload.

    Returns {cik, ticker, company, sic, sic_description, exchange} with missing fields as None. ``company`` is
    the submissions ``name`` (the authoritative legal name); ``exchange`` is the first listed exchange. A missing
    field is None, not an error — the submissions call itself succeeding is what the land asset gates on.
    """
    s = submissions_json or {}
    exchanges = s.get("exchanges") or []
    return {
        "cik": cik,
        "ticker": ticker,
        "company": s.get("name"),
        "sic": s.get("sic"),
        "sic_description": s.get("sicDescription"),
        "exchange": exchanges[0] if exchanges else None,
    }


def parse_company_filings(cik, ticker, submissions_json):
    """Pull the 10-K/10-Q filing history from a company's submissions payload — the Neo4j graph's Filing nodes.

    ``filings.recent`` is column-oriented (parallel arrays: accessionNumber, form, filingDate, reportDate, …), so
    a row is assembled by index. Only ``TARGET_FORMS`` (10-K / 10-Q) are kept, which bounds it to the periodic
    reports (~45 per company). Returns [{cik, ticker, accn, form, filed (date), report_date (date|None)}, ...];
    a filer with no recent filings yields [].
    """
    recent = (((submissions_json or {}).get("filings") or {}).get("recent")) or {}
    accns = recent.get("accessionNumber") or []
    forms = recent.get("form") or []
    filed = recent.get("filingDate") or []
    reports = recent.get("reportDate") or []
    rows = []
    for i, form in enumerate(forms):
        if form not in TARGET_FORMS:
            continue
        rows.append({
            "cik": cik,
            "ticker": ticker,
            "accn": accns[i] if i < len(accns) else None,
            "form": form,
            "filed": parse_edgar_date(filed[i]) if i < len(filed) else None,
            "report_date": parse_edgar_date(reports[i]) if i < len(reports) else None,
        })
    return rows


def build_financials_table(rows):
    """Tidy/long fact rows → an Arrow table with the fixed company_financials silver schema.

    Explicit column types (not inferred) so an all-null value column or an empty run still produces the canonical
    schema the store loaders and the dbt mart expect — the same guarantee ``fred_parse.build_macro_table`` gives.
    """
    def col(name):
        return [r.get(name) for r in rows]

    return pa.table({
        "cik": pa.array(col("cik"), type=pa.int64()),
        "ticker": pa.array(col("ticker"), type=pa.string()),
        "company": pa.array(col("company"), type=pa.string()),
        "concept": pa.array(col("concept"), type=pa.string()),
        "unit": pa.array(col("unit"), type=pa.string()),
        "period_end": pa.array(col("period_end"), type=pa.date32()),
        "fy": pa.array(col("fy"), type=pa.int64()),
        "fp": pa.array(col("fp"), type=pa.string()),
        "form": pa.array(col("form"), type=pa.string()),
        "filed": pa.array(col("filed"), type=pa.date32()),
        "value": pa.array(col("value"), type=pa.float64()),
    })


def build_meta_table(metas):
    """Company-meta dicts → the company_meta dim Arrow table (cik:int64, everything else string)."""
    return pa.table({
        "cik": pa.array([m.get("cik") for m in metas], type=pa.int64()),
        "ticker": pa.array([m.get("ticker") for m in metas], type=pa.string()),
        "company": pa.array([m.get("company") for m in metas], type=pa.string()),
        "sic": pa.array([m.get("sic") for m in metas], type=pa.string()),
        "sic_description": pa.array([m.get("sic_description") for m in metas], type=pa.string()),
        "exchange": pa.array([m.get("exchange") for m in metas], type=pa.string()),
    })


def build_filings_table(rows):
    """Filing rows → the company_filings Arrow table (cik:int64, dates:date32, rest string)."""
    def col(name):
        return [r.get(name) for r in rows]

    return pa.table({
        "cik": pa.array(col("cik"), type=pa.int64()),
        "ticker": pa.array(col("ticker"), type=pa.string()),
        "accn": pa.array(col("accn"), type=pa.string()),
        "form": pa.array(col("form"), type=pa.string()),
        "filed": pa.array(col("filed"), type=pa.date32()),
        "report_date": pa.array(col("report_date"), type=pa.date32()),
    })
