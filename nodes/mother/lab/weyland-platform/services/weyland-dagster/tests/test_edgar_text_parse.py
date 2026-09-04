"""Tests for the dagster-free ``edgar_text_parse`` chunker (B113 Phase 3 — filings-text RAG).

The chunker turns a 10-K's plain text (HTML already stripped by the lander) into section-tagged chunk rows
for the vector fan-out. Section detection is the risky part: a 10-K's Item headings are just inconsistently
worded bold text, and the same "Item 1A" string also appears in the table of contents and in prose
cross-references ("as described in Item 1A of this Form..."). Getting that wrong fails SILENTLY — a mis-tagged
or missing section looks identical to a good one — so these tests pin the discriminators observed on a real
Apple 10-K: a real heading is ``Item <n>. <canonical-title>`` (title adjacent), the TOC entry is an earlier
duplicate (so the LAST occurrence wins), and a prose cross-reference never has the title adjacent.
"""

# A synthetic 10-K shaped like the real one: a TOC cluster, then the body sections, plus a prose cross-ref
# and a trailing Item 8 that must BOUND Item 7 without itself being emitted.
FILING = (
    "APPLE INC. FORM 10-K\n"
    # --- table of contents: every item appears here first, clustered, with no body ---
    "TABLE OF CONTENTS  Item 1. Business 1  Item 1A. Risk Factors 5  "
    "Item 3. Legal Proceedings 18  Item 7. Management's Discussion and Analysis 20  "
    "Item 8. Financial Statements 30\n"
    # --- real body sections ---
    "Item 1. Business " + ("The Company designs and sells smartphones. " * 40) + "\n"
    "Item 1A. Risk Factors " + ("The Company is exposed to macroeconomic risk. " * 60)
    + " As described in Item 1A of this Form under the heading Risk Factors, competition is intense. \n"
    "Item 3. Legal Proceedings " + ("The Company is subject to various claims. " * 20) + "\n"
    "Item 7. Management's Discussion and Analysis " + ("Net sales increased year over year. " * 50) + "\n"
    "Item 8. Financial Statements " + ("See the consolidated balance sheets. " * 30) + "\n"
)

META = dict(cik=320193, ticker="AAPL", accn="0000320193-25-000079", form="10-K", filed="2025-10-31")


def test_detects_the_narrative_sections(edgar_text_parse):
    secs = {s["section"] for s in edgar_text_parse.split_sections(FILING)}
    assert "Business" in secs
    assert "Risk Factors" in secs
    assert "Management Discussion & Analysis" in secs
    assert "Legal Proceedings" in secs


def test_item_8_bounds_item_7_but_is_not_emitted(edgar_text_parse):
    secs = edgar_text_parse.split_sections(FILING)
    names = [s["section"] for s in secs]
    assert "Financial Statements" not in names  # detected only as a boundary, never emitted
    mdna = next(s for s in secs if s["section"] == "Management Discussion & Analysis")
    # its body must stop before the Item 8 text (no balance-sheet leakage)
    assert "balance sheets" not in mdna["text"]
    assert "Net sales increased" in mdna["text"]


def test_toc_and_prose_crossref_do_not_create_phantom_sections(edgar_text_parse):
    secs = edgar_text_parse.split_sections(FILING)
    # exactly one Risk Factors section (not the TOC entry, not the "as described in Item 1A" prose ref)
    risk = [s for s in secs if s["section"] == "Risk Factors"]
    assert len(risk) == 1
    assert "exposed to macroeconomic risk" in risk[0]["text"]  # the body, not the 1-line TOC entry


def test_chunk_filing_emits_tagged_rows_with_sequential_ids(edgar_text_parse):
    rows = edgar_text_parse.chunk_filing(FILING, chunk_size=300, overlap=50, **META)
    assert rows, "expected chunks"
    assert [r["chunk_id"] for r in rows] == list(range(len(rows)))  # 0..n-1, gapless
    for r in rows:
        assert r["cik"] == 320193 and r["ticker"] == "AAPL" and r["accn"] == META["accn"]
        assert r["section"] in {"Business", "Risk Factors", "Legal Proceedings",
                                 "Management Discussion & Analysis",
                                 "Quantitative and Qualitative Disclosures About Market Risk"}
        assert 0 < len(r["text"]) <= 300 + 40  # honors chunk_size (small word-boundary slack)


def test_overlap_carries_context_between_chunks(edgar_text_parse):
    rows = edgar_text_parse.chunk_filing(FILING, chunk_size=300, overlap=80, **META)
    biz = [r["text"] for r in rows if r["section"] == "Business"]
    assert len(biz) >= 2  # the long Business body must split
    # consecutive chunks share a tail/head word run (overlap), so the join isn't a hard cut
    assert biz[0].split()[-1] in biz[1]


def test_fallback_to_whole_doc_when_no_sections_detected(edgar_text_parse):
    plain = "This document has no recognizable SEC item headings at all. " * 30
    rows = edgar_text_parse.chunk_filing(plain, chunk_size=300, overlap=50, **META)
    assert rows
    assert all(r["section"] == "FULL" for r in rows)  # fallback tag, still chunked + tagged


def test_no_chunk_is_empty_or_whitespace(edgar_text_parse):
    rows = edgar_text_parse.chunk_filing(FILING, chunk_size=300, overlap=50, **META)
    assert all(r["text"].strip() for r in rows)
