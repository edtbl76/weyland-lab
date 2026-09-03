"""Tests for the dagster-free ``edgar_parse`` leaf module (B113 Phase 2, finance domain).

Loaded in isolation via the ``edgar_parse`` fixture — proves the fast lane never imports the dagster
runtime. Covers the concept→label mapping, the revenue fallback (newer filers report
RevenueFromContractWithCustomerExcludingAssessedTax instead of Revenues), form filtering (only 10-K/10-Q),
dedup-by-latest-filed (a restated fact must not double-count), the SIC extraction from submissions, and the
curated 50-company selection.

Every fixture below is CRAFTED sample JSON in the exact API shape confirmed live on 2026-09-03 — the
committed tests require NO network and NO User-Agent.
"""
import datetime

import pytest


# --- crafted SEC payloads (verbatim shape from the live API, values abbreviated) -------------------

# AAPL-like: reports the OLD ``Revenues`` concept plus net income, assets, and a restated net-income row
# (same period, later filed) that must WIN the dedup. Includes a 10-Q row and a bogus 8-K row that must be
# FILTERED OUT by the form restriction.
_FACTS_OLD_REVENUE = {
    "facts": {
        "us-gaap": {
            "Revenues": {"units": {"USD": [
                {"end": "2023-12-31", "val": 383285000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01", "accn": "a1"},
                {"end": "2024-03-31", "val": 90753000000, "fy": 2024, "fp": "Q1", "form": "10-Q", "filed": "2024-05-01", "accn": "a2"},
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                # two 10-K/FY rows for the SAME period_end — the LATER-filed restatement must win the dedup.
                {"end": "2023-12-31", "val": 96000000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01", "accn": "a1"},
                {"end": "2023-12-31", "val": 97000000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "accn": "a9"},
                # an 8-K row must be dropped by the form filter.
                {"end": "2023-12-31", "val": 12345, "fy": 2023, "fp": "FY", "form": "8-K", "filed": "2024-12-01", "accn": "aX"},
            ]}},
            "Assets": {"units": {"USD": [
                {"end": "2023-12-31", "val": 352583000000, "fy": 2023, "fp": "FY", "form": "10-K", "filed": "2024-02-01", "accn": "a1"},
            ]}},
        }
    }
}

# NVDA-like newer filer: reports ONLY the NEW revenue concept (no ``Revenues``) → the fallback must fire.
# Also carries a missing value (literal ".") that must coerce to None, not raise.
_FACTS_NEW_REVENUE = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                {"end": "2024-01-28", "val": 60922000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-02-21", "accn": "n1"},
            ]}},
            "EarningsPerShareBasic": {"units": {"USD/shares": [
                {"end": "2024-01-28", "val": ".", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-02-21", "accn": "n1"},
            ]}},
        }
    }
}

_SUBMISSIONS = {
    "cik": 320193,
    "name": "Apple Inc.",
    "sic": "3571",
    "sicDescription": "Electronic Computers",
    "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"],
}

_TICKERS = {str(i): {"cik_str": 1000 + i, "ticker": f"T{i}", "title": f"Company {i}"} for i in range(60)}


# --- select_ciks ------------------------------------------------------------------------------------

def test_select_ciks_takes_first_50(edgar_parse):
    ciks = edgar_parse.select_ciks(_TICKERS)
    assert len(ciks) == edgar_parse.CIK_COUNT == 50
    # first tuple, ordered by the numeric index key, is (cik:int, ticker, title)
    assert ciks[0] == (1000, "T0", "Company 0")
    assert all(isinstance(c[0], int) for c in ciks)


def test_select_ciks_orders_by_numeric_key_not_string(edgar_parse):
    # keys "2" and "10" must order 2 < 10 (numeric), not lexicographically ("10" < "2").
    tickers = {"10": {"cik_str": 10, "ticker": "TEN", "title": "Ten"},
               "2": {"cik_str": 2, "ticker": "TWO", "title": "Two"}}
    ciks = edgar_parse.select_ciks(tickers)
    assert [c[1] for c in ciks] == ["TWO", "TEN"]


def test_select_ciks_empty_fails_closed(edgar_parse):
    # A ticker map that returned nothing is a real failure — must RAISE with a reason (assert the REASON).
    with pytest.raises(ValueError, match="no entries"):
        edgar_parse.select_ciks({})


# --- parse_company_financials: mapping, form filter, dedup ------------------------------------------

def test_parse_financials_maps_concepts_and_filters_forms(edgar_parse):
    rows = edgar_parse.parse_company_financials(320193, "AAPL", "Apple Inc.", _FACTS_OLD_REVENUE)
    by = {(r["concept"], r["period_end"], r["form"]): r for r in rows}
    # clean snake labels, not the raw us-gaap concept names
    concepts = {r["concept"] for r in rows}
    assert concepts == {"revenue", "net_income", "assets"}
    # the 10-Q revenue row is KEPT (10-Q is a target form); the 8-K net-income row is DROPPED.
    assert ("revenue", datetime.date(2024, 3, 31), "10-Q") in by
    assert not any(r["form"] == "8-K" for r in rows)
    # row shape carries the full tidy schema
    r = by[("assets", datetime.date(2023, 12, 31), "10-K")]
    assert r["cik"] == 320193 and r["ticker"] == "AAPL" and r["company"] == "Apple Inc."
    assert r["unit"] == "USD" and r["fy"] == 2023 and r["fp"] == "FY"
    assert r["value"] == pytest.approx(352583000000.0)
    assert r["filed"] == datetime.date(2024, 2, 1)


def test_parse_financials_dedups_to_latest_filed(edgar_parse):
    # EDGE CASE 1: two 10-K/FY net-income rows for the same period — the LATER-filed restatement wins.
    rows = edgar_parse.parse_company_financials(320193, "AAPL", "Apple Inc.", _FACTS_OLD_REVENUE)
    ni = [r for r in rows if r["concept"] == "net_income" and r["form"] == "10-K"]
    assert len(ni) == 1
    assert ni[0]["value"] == pytest.approx(97000000000.0)   # the 2024-11-01 restatement, not 2024-02-01
    assert ni[0]["filed"] == datetime.date(2024, 11, 1)


def test_parse_financials_revenue_fallback_concept(edgar_parse):
    # EDGE CASE 2: a newer filer with NO ``Revenues`` — the RevenueFromContractWithCustomer… fallback fires,
    # still mapped to the clean ``revenue`` label.
    rows = edgar_parse.parse_company_financials(1045810, "NVDA", "NVIDIA Corp", _FACTS_NEW_REVENUE)
    rev = [r for r in rows if r["concept"] == "revenue"]
    assert len(rev) == 1
    assert rev[0]["value"] == pytest.approx(60922000000.0)


def test_parse_financials_revenue_unions_old_and_new_concepts(edgar_parse):
    # REGRESSION: a filer that reports the OLD ``Revenues`` for an old period AND the NEW contract-revenue
    # concept for a recent one (Apple's ``Revenues`` stops at 2018) must yield BOTH periods under ``revenue`` —
    # "first present concept wins" silently dropped the recent revenue and the mart's revenue went null.
    facts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            {"end": "2017-09-30", "val": 229234000000, "fy": 2017, "fp": "FY", "form": "10-K", "filed": "2017-11-03", "accn": "o1"},
        ]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            {"end": "2024-09-28", "val": 391035000000, "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2024-11-01", "accn": "o2"},
        ]}},
    }}}
    rows = edgar_parse.parse_company_financials(320193, "AAPL", "Apple Inc.", facts)
    rev_ends = {r["period_end"] for r in rows if r["concept"] == "revenue"}
    assert datetime.date(2017, 9, 30) in rev_ends
    assert datetime.date(2024, 9, 28) in rev_ends   # the recent one first-present-wins used to drop


def test_parse_financials_missing_value_dot_is_null(edgar_parse):
    # a literal "." value must coerce to None (not raise), same gotcha as FRED.
    rows = edgar_parse.parse_company_financials(1045810, "NVDA", "NVIDIA Corp", _FACTS_NEW_REVENUE)
    eps = [r for r in rows if r["concept"] == "eps_basic"]
    assert len(eps) == 1
    assert eps[0]["value"] is None


def test_parse_financials_missing_concept_skipped_not_crash(edgar_parse):
    # a company that reported none of the target concepts yields no rows — must not crash.
    rows = edgar_parse.parse_company_financials(1, "X", "X Co", {"facts": {"us-gaap": {}}})
    assert rows == []
    # and a totally empty payload is handled too
    assert edgar_parse.parse_company_financials(1, "X", "X Co", {}) == []


# --- parse_company_meta -----------------------------------------------------------------------------

def test_parse_company_meta_extracts_sic_and_exchange(edgar_parse):
    meta = edgar_parse.parse_company_meta(320193, "AAPL", _SUBMISSIONS)
    assert meta == {
        "cik": 320193,
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "sic": "3571",
        "sic_description": "Electronic Computers",
        "exchange": "Nasdaq",
    }


def test_parse_company_meta_missing_fields_are_none(edgar_parse):
    meta = edgar_parse.parse_company_meta(7, "Z", {"name": "Zed"})
    assert meta["company"] == "Zed"
    assert meta["sic"] is None and meta["sic_description"] is None and meta["exchange"] is None


# --- build tables: fixed typed silver schema -------------------------------------------------------

def test_build_financials_table_has_the_fixed_typed_schema(edgar_parse):
    import pyarrow as pa

    rows = edgar_parse.parse_company_financials(320193, "AAPL", "Apple Inc.", _FACTS_OLD_REVENUE)
    t = edgar_parse.build_financials_table(rows)
    assert list(t.column_names) == list(edgar_parse.FINANCIALS_COLUMNS)
    assert t.schema.field("cik").type == pa.int64()
    assert t.schema.field("period_end").type == pa.date32()
    assert t.schema.field("filed").type == pa.date32()
    assert t.schema.field("value").type == pa.float64()
    assert t.num_rows == len(rows)


def test_build_financials_table_empty_still_yields_schema(edgar_parse):
    t = edgar_parse.build_financials_table([])
    assert list(t.column_names) == list(edgar_parse.FINANCIALS_COLUMNS)
    assert t.num_rows == 0


def test_build_meta_table_schema_and_values(edgar_parse):
    metas = [edgar_parse.parse_company_meta(320193, "AAPL", _SUBMISSIONS)]
    t = edgar_parse.build_meta_table(metas)
    assert list(t.column_names) == list(edgar_parse.META_COLUMNS)
    assert t.column("cik").to_pylist() == [320193]
    assert t.column("sic").to_pylist() == ["3571"]
    assert t.column("exchange").to_pylist() == ["Nasdaq"]


# --- allowlist constants (what the transform config unions with the FRED ones) ---------------------

def test_edgar_allowlists_are_internally_consistent(edgar_parse):
    assert edgar_parse.EDGAR_TABLES == ("company_financials", "company_meta")
    assert edgar_parse.EDGAR_RAW_TABLES == {"company_financials", "company_meta"}
    assert edgar_parse.EDGAR_CLICKHOUSE_ALLOW == {"company_financials", "company_meta"}
    assert edgar_parse.EDGAR_ICEBERG_ALLOW == {"company_financials", "company_meta"}
    assert set(edgar_parse.CONCEPTS) == {
        "revenue", "net_income", "assets", "liabilities",
        "stockholders_equity", "eps_basic", "shares_outstanding",
    }
    # the revenue label carries its fallback concept second
    assert edgar_parse.CONCEPTS["revenue"] == (
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    )
