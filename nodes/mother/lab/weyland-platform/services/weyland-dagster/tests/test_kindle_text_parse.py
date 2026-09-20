"""Tests for the dagster-free ``kindle_text_parse`` book chunker (B165 — Kindle-library RAG).

Mirrors ``test_edgar_text_parse``. The risky parts here are (1) pulling readable text + title/author out of an
EPUB — a zip of namespaced OPF/XHTML that varies by producer — without leaking script/style or running chapters
together, (2) falling back to reading raw (x)html entries when the OPF spine can't be resolved (never returning
nothing for a non-empty book), and (3) chunking chapter-aware with the same greedy overlap contract as finance.
A synthetic in-memory EPUB keeps the test hermetic (no network, no shipped book file).
"""
import io
import zipfile

CONTAINER = (
    '<?xml version="1.0"?>'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>'
    "</container>"
)

OPF = (
    '<?xml version="1.0"?>'
    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
    "<dc:title>Pride and Prejudice</dc:title><dc:creator>Jane Austen</dc:creator></metadata>"
    '<manifest>'
    '<item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
    '<item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/>'
    "</manifest>"
    '<spine><itemref idref="c1"/><itemref idref="c2"/></spine>'
    "</package>"
)


def _chapter(heading, body):
    return (
        "<html><head><title>%s</title><style>.x{color:red}</style></head>"
        "<body><h1>%s</h1><p>%s</p><script>window.evil='SHOULD_NOT_APPEAR'</script></body></html>"
        % (heading, heading, body)
    )


def _make_epub(*, with_container=True, with_opf=True):
    buf = io.BytesIO()
    ch1 = _chapter("Chapter One", "It is a truth universally acknowledged that a single man. " * 60)
    ch2 = _chapter("Chapter Two", "Mr Bennet was among the earliest of those who waited on Mr Bingley. " * 60)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip")
        if with_container:
            z.writestr("META-INF/container.xml", CONTAINER)
        if with_opf:
            z.writestr("OEBPS/content.opf", OPF)
        z.writestr("OEBPS/ch1.xhtml", ch1)
        z.writestr("OEBPS/ch2.xhtml", ch2)
    return buf.getvalue()


def test_extract_epub_reads_metadata_and_chapters_in_spine_order(kindle_text_parse):
    title, author, chapters = kindle_text_parse.extract_epub(_make_epub())
    assert title == "Pride and Prejudice"
    assert author == "Jane Austen"
    assert [c[0] for c in chapters] == ["ch1.xhtml", "ch2.xhtml"]  # spine order
    assert "universally acknowledged" in chapters[0][1]
    assert "earliest of those" in chapters[1][1]


def test_extract_epub_drops_script_style_and_does_not_run_text_together(kindle_text_parse):
    _, _, chapters = kindle_text_parse.extract_epub(_make_epub())
    body = chapters[0][1]
    assert "SHOULD_NOT_APPEAR" not in body        # script contents stripped
    assert "color:red" not in body                # style contents stripped
    assert "Chapter One It is a truth" in body     # heading + para separated by a space, not glued


def test_extract_epub_falls_back_when_opf_spine_unresolvable(kindle_text_parse):
    # No container.xml + no OPF → the spine can't be resolved; must still read the xhtml entries, not return nothing.
    _, _, chapters = kindle_text_parse.extract_epub(_make_epub(with_container=False, with_opf=False))
    assert chapters, "fallback must read raw (x)html entries"
    joined = " ".join(c[1] for c in chapters)
    assert "universally acknowledged" in joined and "earliest of those" in joined


def test_chunk_book_tags_chapters_with_gapless_ids_and_honors_size(kindle_text_parse):
    _, _, chapters = kindle_text_parse.extract_epub(_make_epub())
    rows = kindle_text_parse.chunk_book(chapters, book_id="pride", title="Pride and Prejudice",
                                        author="Jane Austen", chunk_size=300, overlap=60)
    assert rows
    assert [r["chunk_id"] for r in rows] == list(range(len(rows)))  # 0..n-1, gapless across the whole book
    assert {r["section"] for r in rows} == {"ch1.xhtml", "ch2.xhtml"}
    for r in rows:
        assert r["book_id"] == "pride" and r["title"] == "Pride and Prejudice" and r["author"] == "Jane Austen"
        assert 0 < len(r["text"]) <= 300 + 40  # honors chunk_size with small word-boundary slack
        assert r["text"].strip()               # no empty/whitespace chunk


def test_chunk_book_overlap_carries_context(kindle_text_parse):
    _, _, chapters = kindle_text_parse.extract_epub(_make_epub())
    rows = kindle_text_parse.chunk_book(chapters, book_id="p", title="t", author="a", chunk_size=300, overlap=80)
    ch1 = [r["text"] for r in rows if r["section"] == "ch1.xhtml"]
    assert len(ch1) >= 2                       # the long chapter must split
    assert ch1[0].split()[-1] in ch1[1]        # consecutive chunks share a word run (overlap, not a hard cut)


def test_extract_txt_is_one_full_section(kindle_text_parse):
    title, author, sections = kindle_text_parse.extract_txt("notes/My Doc.txt", b"line one\n\nline  two   three")
    assert title == "My Doc" and author == ""
    assert sections == [("FULL", "line one line two three")]  # whitespace normalized, single section


def test_extract_and_chunk_dispatches_on_extension(kindle_text_parse):
    epub_rows = kindle_text_parse.extract_and_chunk("Pride and Prejudice.epub", _make_epub(), chunk_size=400, overlap=60)
    assert epub_rows and {r["section"] for r in epub_rows} == {"ch1.xhtml", "ch2.xhtml"}
    assert epub_rows[0]["title"] == "Pride and Prejudice"        # from OPF metadata
    txt_rows = kindle_text_parse.extract_and_chunk("essay.txt", b"a short personal note. " * 50, chunk_size=200, overlap=40)
    assert txt_rows and all(r["section"] == "FULL" for r in txt_rows)
    assert txt_rows[0]["title"] == "essay"                       # from the filename
