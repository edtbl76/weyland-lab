"""Fuzz / robustness tests (B152 category 6) — the one parser that ingests untrusted external input.

`edgar_text_parse` turns raw SEC 10-K HTML/text into chunk rows. It must NEVER crash, hang, or violate its
output contract on arbitrary or malformed input. hypothesis generates adversarial text (control chars, full
unicode, HTML junk, empty, whitespace-only, very long); the `@example`s pin known-nasty shapes. The module
is stdlib-only (`re`) and dagster-free, so this runs in the slim lane. The suite completing at all also
proves the greedy chunker terminates (it claims "always makes forward progress")."""
import importlib.util
import pathlib

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(relpath: str, name: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


etp = _load("weyland_pipeline/assets/datasets_lib/edgar_text_parse.py", "fuzz_edgar_text_parse")

# Adversarial text: the full unicode range including control characters, plus size stress.
_fuzz_text = st.text(alphabet=st.characters(), max_size=4000)

_META = dict(cik="0000000000", ticker="TST", accn="0000-00-000000", form="10-K", filed="2026-01-01")
_ROW_KEYS = {"cik", "ticker", "accn", "form", "filed", "section", "chunk_id", "text"}


@example("")
@example("     \t\n  ")
@example("<html><body><p>Item 1. Business</p> junk <div>Item 1A. Risk Factors</div> more</body></html>")
@example("Item 1. Business\x00\x01\x02 body Item 1A. Risk Factors﻿​ more Item 7. MD&A tail")
@example("word " * 5000)  # one giant section → many chunks
@given(text=_fuzz_text)
@settings(max_examples=250, suppress_health_check=[HealthCheck.large_base_example], deadline=None)
def test_chunk_filing_never_crashes_and_contract_holds(text):
    rows = etp.chunk_filing(text, **_META)
    assert isinstance(rows, list)
    for i, r in enumerate(rows):
        assert set(r) == _ROW_KEYS, f"row {i} keys drifted: {set(r)}"
        # every chunk is a non-empty, stripped string
        assert isinstance(r["text"], str) and r["text"] and r["text"] == r["text"].strip()
        # chunk_id is a stable sequential index across the whole filing
        assert r["chunk_id"] == i
        # the caller's metadata is preserved verbatim, never mangled by parsing
        assert (r["cik"], r["ticker"], r["accn"], r["form"], r["filed"]) == (
            _META["cik"], _META["ticker"], _META["accn"], _META["form"], _META["filed"],
        )


@given(text=_fuzz_text)
@settings(max_examples=250, suppress_health_check=[HealthCheck.large_base_example], deadline=None)
def test_split_sections_never_crashes(text):
    secs = etp.split_sections(text)
    assert isinstance(secs, list)
    for s in secs:
        assert "text" in s and "section" in s and isinstance(s["text"], str)
