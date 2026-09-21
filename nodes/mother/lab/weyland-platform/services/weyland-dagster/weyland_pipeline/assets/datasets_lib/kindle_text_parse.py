"""Chapter-aware chunker for book text — EPUB/TXT → RAG chunk rows (B165 — Kindle-library RAG).

Dagster-free and light-dependency (``zipfile``/``html``/``re`` from the stdlib + ``defusedxml`` for the EPUB XML,
which guards against a malicious book's XXE / billion-laughs payload — stdlib ``xml.etree`` is vulnerable by
default). Absolute imports — so it loads in the light test lane in isolation, the same contract as
``edgar_text_parse.py`` (the finance-filings sibling this mirrors).
The extraction VM strips DRM and lands EPUB/TXT in MinIO; this module turns those files into the tidy ``books``
raw table the vector fan-out embeds.

Why chapter-aware: a book already carries real structure (the EPUB spine is the chapter reading order), so we
segment on it and tag each chunk with its chapter — the book analogue of the 10-K's section-aware split. The
greedy word-boundary chunker itself (overlap, forward-progress) is IDENTICAL to the finance one and copied
verbatim (``_chunk_text``) — a leaf uses absolute imports only, so it can't sibling-import it. TXT (a personal doc
with no spine) is chunked as one ``FULL`` section.
"""
import html
import io as _io
import re
import zipfile
from html.parser import HTMLParser

from defusedxml.ElementTree import fromstring  # XXE/billion-laughs-safe XML parse for untrusted EPUB metadata

# The single books table — the transform config imports this one name (mirrors FILINGS_TEXT_TABLES).
KINDLE_TEXT_TABLES = frozenset({"books"})

_WS = re.compile(r"\s+")


def _chunk_text(body, chunk_size, overlap):
    """Greedy word-boundary chunks of at most ``chunk_size`` chars, each carrying ~``overlap`` chars of the
    previous chunk's tail so context isn't hard-cut. Always makes forward progress.

    COPIED VERBATIM from ``edgar_text_parse._chunk_text`` on purpose: a leaf module in ``datasets_lib`` must use
    absolute imports only (it is loaded in isolation by the test harness's ``load_isolated`` and the B152 arch
    contract forbids the ``from .`` sibling import), so the shared chunker is duplicated rather than imported.
    Keep the two in sync; they are byte-identical."""
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


def _local(tag):
    """ElementTree tag without its ``{namespace}`` — OPF/XHTML are namespaced and vary by producer."""
    return tag.rsplit("}", 1)[-1].lower()


class _TextStripper(HTMLParser):
    """Collect visible text from an (X)HTML chapter, dropping script/style, inserting spaces at block edges so
    adjacent blocks don't run together (the chunker then normalizes whitespace)."""
    _SKIP = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1
        self._parts.append(" ")  # block edge → separator

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def text(self):
        return _WS.sub(" ", html.unescape("".join(self._parts))).strip()


def _strip_html(raw):
    p = _TextStripper()
    try:
        p.feed(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw)
    except Exception:  # noqa: BLE001 — a malformed chapter yields whatever text parsed so far, never aborts the book
        pass
    return p.text()


def _opf_path(zf, names):
    """The OPF manifest path from META-INF/container.xml, or None."""
    if "META-INF/container.xml" not in names:
        return None
    root = fromstring(zf.read("META-INF/container.xml"))
    for el in root.iter():
        if _local(el.tag) == "rootfile" and el.get("full-path"):
            return el.get("full-path")
    return None


def _parse_opf_spine(zf, opf_path, names):
    """Parse the OPF: title, author, and the chapters in spine (reading) order. Returns (title, author, chapters)."""
    opf = fromstring(zf.read(opf_path))
    base = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
    title, author, manifest, spine = "", "", {}, []
    for el in opf.iter():
        lt = _local(el.tag)
        if lt == "title" and not title:
            title = (el.text or "").strip()
        elif lt == "creator" and not author:
            author = (el.text or "").strip()
        elif lt == "item":
            manifest[el.get("id")] = el.get("href")
        elif lt == "itemref" and el.get("idref"):
            spine.append(el.get("idref"))
    chapters = []
    for idref in spine:
        href = manifest.get(idref)
        if not href:
            continue
        full = (f"{base}/{href}" if base else href).split("#", 1)[0]
        if full not in names:
            continue
        text = _strip_html(zf.read(full))
        if text:
            chapters.append((href.rsplit("/", 1)[-1], text))
    return title, author, chapters


def _all_html_chapters(zf, names):
    """Fallback: every (x)html entry in archive order → chapters. Used when the OPF spine can't be resolved."""
    chapters = []
    for n in names:
        if n.lower().endswith((".xhtml", ".html", ".htm")):
            text = _strip_html(zf.read(n))
            if text:
                chapters.append((n.rsplit("/", 1)[-1], text))
    return chapters


def extract_epub(data):
    """Parse an EPUB (a zip) → ``(title, author, [(chapter_title, text)])`` in spine (reading) order, using only
    the stdlib. Falls back to reading every (x)html entry when the OPF spine can't be resolved — never returns
    nothing for a non-empty book."""
    zf = zipfile.ZipFile(_io.BytesIO(data))
    names = zf.namelist()
    title, author, chapters = "", "", []
    opf_path = _opf_path(zf, names)
    if opf_path and opf_path in names:
        title, author, chapters = _parse_opf_spine(zf, opf_path, names)
    if not chapters:  # no resolvable spine → read every (x)html entry in archive order
        chapters = _all_html_chapters(zf, names)
    return title, author, chapters


def extract_txt(name, data):
    """A personal-doc TXT → ``(title, author, [("FULL", text)])``. Title from the filename; no chapter structure."""
    text = _WS.sub(" ", (data.decode("utf-8", "replace") if isinstance(data, bytes) else data)).strip()
    title = re.sub(r"\.[^.]+$", "", name.rsplit("/", 1)[-1])
    return title, "", ([("FULL", text)] if text else [])


def chunk_book(sections, *, book_id, title, author, chunk_size=1200, overlap=200):
    """Chapter-aware chunk rows for one book. ``sections`` is ``[(chapter_title, text)]``; each chapter is greedily
    chunked with overlap, tagged with its chapter as ``section`` and a monotonic ``chunk_id`` across the book.
    Returns ``[]`` for a book with no text (the caller fail-closes on an empty land)."""
    rows, cid = [], 0
    for section, text in sections:
        for chunk in _chunk_text(text, chunk_size, overlap):
            chunk = chunk.strip()
            if not chunk:
                continue
            rows.append({
                "book_id": book_id, "title": title, "author": author,
                "section": section, "chunk_id": cid, "text": chunk,
            })
            cid += 1
    return rows


def extract_and_chunk(object_name, data, **kw):
    """Dispatch on extension → chunk rows. book_id is the file's basename sans extension (stable, human-readable)."""
    book_id = re.sub(r"\.[^.]+$", "", object_name.rsplit("/", 1)[-1])
    if object_name.lower().endswith(".epub"):
        title, author, sections = extract_epub(data)
    else:
        title, author, sections = extract_txt(object_name, data)
    return chunk_book(sections, book_id=book_id, title=(title or book_id), author=author, **kw)
