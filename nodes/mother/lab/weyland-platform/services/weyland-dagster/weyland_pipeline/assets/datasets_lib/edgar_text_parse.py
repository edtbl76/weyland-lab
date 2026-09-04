"""Section-aware chunker for SEC 10-K filing text (B113 Phase 3 — filings-text RAG).

Dagster-free, stdlib-only (``re``), absolute imports — so it loads in the light test lane in isolation (same
contract as ``edgar_parse.py``/``mongo_encode.py``). The lander strips the filing HTML to plain text (bs4) and
hands it here; this module segments the narrative Items and chunks them for the vector fan-out.

Why section-aware, and why it's careful: a 10-K's Item headings are just inconsistently-worded bold text, and
the same "Item 1A" string also appears in the table of contents and in prose cross-references ("as described
in Item 1A of this Form ... Risk Factors"). A naive splitter mis-tags or drops sections SILENTLY. The
discriminators here were validated against a real Apple 10-K (FY2025, aapl-20250927.htm):

  * a real heading is ``Item <n>. <canonical-title>`` with the title ADJACENT to the number;
  * the table-of-contents entry is an earlier duplicate of that exact string, so the LAST occurrence of each
    item is its body heading (the TOC one is skipped);
  * a prose cross-reference never places the canonical title adjacent to the number, so it never matches.

The FULL standard item set is detected to BOUND section ends; only the narrative subset (Business / Risk
Factors / Legal Proceedings / MD&A / Market Risk) is emitted as content — the structured financials already
live in the Phase-2 XBRL mart, so Item 8's tables add noise, not signal, to a text-RAG corpus. When fewer than
two sections are detected (an unusual layout), the whole document is chunked under the ``FULL`` tag rather than
silently returning nothing.
"""
import re

# Phase 3: the single filings-text table. Joins the raw silver formats + Iceberg gold + the vector fan-out
# (declared here so the transform config imports one name, mirroring EDGAR_RAW_TABLES in edgar_parse).
FILINGS_TEXT_TABLES = frozenset({"filings_text"})

# Canonical 10-K Item titles. The whole set is detected so a section's body ends at the NEXT item; only the
# EMIT subset (SECTION_NAMES) is kept as content.
_TITLES = {
    "1":  r"business",
    "1A": r"risk\s+factors",
    "1B": r"unresolved\s+staff\s+comments",
    "1C": r"cybersecurity",
    "2":  r"properties",
    "3":  r"legal\s+proceedings",
    "4":  r"mine\s+safety",
    "5":  r"market\s+for",
    "6":  r"(?:reserved|selected\s+financial)",
    "7":  r"management.s\s+discussion",
    "7A": r"quantitative\s+and\s+qualitative",
    "8":  r"financial\s+statements",
    "9":  r"changes\s+in\s+and",
    "9A": r"controls\s+and\s+procedures",
    "9B": r"other\s+information",
}

SECTION_NAMES = {
    "1":  "Business",
    "1A": "Risk Factors",
    "3":  "Legal Proceedings",
    "7":  "Management Discussion & Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
}
_EMIT = set(SECTION_NAMES)

_WS = re.compile(r"\s+")


def _normalize(text):
    """Collapse NBSP + all whitespace runs to single spaces — 10-K headings pad with NBSP (``Item 1A.\xa0\xa0Risk``)."""
    return _WS.sub(" ", (text or "").replace("\xa0", " ")).strip()


def split_sections(text):
    """Return ``[{item, section, text}]`` for the narrative Items present, each body bounded by the next
    detected Item heading. Bodies are in document order."""
    t = _normalize(text)
    heads = []
    for item, title in _TITLES.items():
        occ = [m.start() for m in re.finditer(r"item\s+%s\.?\s+%s" % (re.escape(item), title), t, re.I)]
        if occ:
            heads.append((occ[-1], item))   # last occurrence = body heading (the earlier one is the TOC)
    heads.sort()
    out = []
    for i, (pos, item) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(t)
        if item in _EMIT:
            body = t[pos:end].strip()
            if body:
                out.append({"item": item, "section": SECTION_NAMES[item], "text": body})
    return out


def _chunk_text(body, chunk_size, overlap):
    """Greedy word-boundary chunks of at most ``chunk_size`` chars, each carrying ~``overlap`` chars of the
    previous chunk's tail so context isn't hard-cut. Always makes forward progress."""
    words = body.split()
    n = len(words)
    chunks = []
    i = 0
    while i < n:
        cur, clen, j = [], 0, i
        while j < n:
            add = len(words[j]) + (1 if cur else 0)
            if cur and clen + add > chunk_size:
                break
            cur.append(words[j])
            clen += add
            j += 1
        chunks.append(" ".join(cur))
        if j >= n:
            break
        # trailing words within `overlap` chars, capped so we never re-emit the whole chunk (guarantees progress)
        ov, olen = [], 0
        for w in reversed(cur):
            add = len(w) + (1 if ov else 0)
            if olen + add > overlap:
                break
            ov.insert(0, w)
            olen += add
        back = min(len(ov), len(cur) - 1)
        i = j - back
    return chunks


def chunk_filing(text, *, cik, ticker, accn, form, filed, chunk_size=1200, overlap=200):
    """Section-aware chunk rows for one filing. Falls back to whole-document chunking (section ``FULL``) when
    fewer than two narrative sections are detected — never returns nothing for a non-empty filing."""
    secs = split_sections(text)
    if len(secs) < 2:
        norm = _normalize(text)
        secs = [{"item": "FULL", "section": "FULL", "text": norm}] if norm else []
    rows = []
    cid = 0
    for s in secs:
        for chunk in _chunk_text(s["text"], chunk_size, overlap):
            chunk = chunk.strip()
            if not chunk:
                continue
            rows.append({
                "cik": cik, "ticker": ticker, "accn": accn, "form": form, "filed": filed,
                "section": s["section"], "chunk_id": cid, "text": chunk,
            })
            cid += 1
    return rows
