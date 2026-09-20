# Runbook — Kindle highlights → KM RAG (B165)

Ingest the owner's **own** Kindle **highlights + notes** as a knowledge-management RAG corpus. Personal use,
LAN-only, $0.

> **Scope note (re-tiered 2026-09-20, HIGH → Medium).** The original goal was FULL book text. That route is
> **dead for this account.** Amazon has locked the old, DeDRM-strippable Kindle-for-PC versions (1.x) out of
> *downloading* content — they sign in but Amazon refuses to serve books ("This version is out of date"), while the
> current app (2.x) downloads fine but its DRM can't be stripped. Proven the hard way 2026-09-20 in a throwaway
> Windows VM: Kindle-for-PC **1.17** wouldn't sign in at all; **1.36** signed in and synced the 188-book library but
> **refused every download**. The extraction spike ([concepts/kindle-rag-eval.md](../concepts/kindle-rag-eval.md))
> flagged exactly this risk. So the corpus is **highlights**, not full text — the highest-signal passages, and no
> DRM circumvention (they're the owner's own annotations). The Windows-VM / DeDRM machinery was removed; the
> ingestion pipeline below is unchanged — it takes highlight text the same as book text. Medium, not the "90% infra"
> easy win, because the highlights extraction + curation is manual.

Two halves:
- **Extraction (highlights):** pull the owner's highlights/notes from `read.amazon.com/notebook` → one text file per
  book → MinIO `kindle-corpus`.
- **Ingestion + query (the cluster half):** unchanged — the weyland-dagster pipeline chunks → bge embeds → writes
  the `kindle` Qdrant/Weaviate collection; query via the operator/MCP, graded against a golden set.

## Extraction — highlights from read.amazon.com/notebook

`https://read.amazon.com/notebook` lists every book that has highlights and shows its highlights + notes for the
signed-in account. There is **no official bulk export**, so this is the manual/semi-automated part (the reason B165
is Medium, not an easy win):

- **Manual:** open the notebook, pick a book, copy its highlights into `<title>.txt`. Fine for a handful of books,
  tedious across a large library.
- **Semi-automated (recommended for a big library):** a browser scrape of the notebook — you log into Amazon once,
  then a script walks the book list and pulls each book's highlights. The lab's **Playwright MCP** can drive this
  (the login is yours; it iterates the books). Output: one `<title>.txt` per book, with a title/author header line
  so the ingestion carries them into the payload.
- **Curation:** highlights are already the passages you chose to mark, so ingesting them all is reasonable; drop any
  you don't want a KM query to surface. That per-book curation is the manual cost of this route.

Land the `.txt` files in MinIO `kindle-corpus` (any S3 client — e.g. `mc cp *.txt weyland/kindle-corpus/` with the
lab's `AWS_*` creds against the LAN endpoint `http://192.168.1.243:30990`), then run the ingestion below.

## The cluster half (ingestion + query) — unchanged

Once `.txt` files are in MinIO `kindle-corpus`, the weyland-dagster `datasets_kindle_*` assets land → chunk (a `.txt`
is chunked whole with overlap; a full EPUB, if ever available, would chunk chapter-aware) → bge embed → write the
**`kindle`** collection to Qdrant/Weaviate with per-book payload (title/author) for filtered retrieval, and emit the
dataset + lineage to DataHub. Deploy is the standard dagster image tag flow (new registry tag + bump `user-code`).
Run the `kindle` **land → hydrate** jobs to build the collection. Query via the operator or the read-only MCP;
retrieval is graded against a `kindle` golden set through the existing eval matrix. The pipeline was proven on a
public-domain Gutenberg EPUB before any real corpus existed. See [demos/kindle-rag.md](../demos/kindle-rag.md) and
[diagrams/flow-kindle-rag.md](../diagrams/flow-kindle-rag.md).

## Legality / scope

The owner's **own** highlights/annotations, personal LAN-only KM use, no redistribution, **no DRM circumvention** —
`read.amazon.com/notebook` exposes the owner's own notes directly. (The abandoned full-text route's DeDRM tooling
was removed; see the scope note above and the spike doc for why.)
