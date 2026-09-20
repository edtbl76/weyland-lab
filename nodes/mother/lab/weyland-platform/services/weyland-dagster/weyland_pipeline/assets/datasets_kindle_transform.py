"""Kindle dataset fan-out transform — the explicit kindle DomainConfig over the shared broker (B165).

Same mechanism as finance/music/health (datasets_lib): the only kindle specifics are the repo, namespace, and
the one text table. Books are a pure text-RAG corpus, so kindle targets ONLY the base silver formats + Iceberg
gold (a Trino-queryable corpus) + the VECTOR stores — no tabular/OLAP/graph stores (a book chunk isn't
relational). build_transform_assets() produces datasets_kindle_parquet/_arrow/_avro/_lance/_iceberg + _commit.

The books table (book_id, title, author, section, chunk_id, text) is landed by datasets_kindle_books_land from
the DRM-stripped EPUB/TXT the extraction VM uploaded to MinIO. `text` is embedded (bge-small 384, the shared
mesh embedder — set EMBED_MODEL=BAAI/bge-base-en-v1.5 to move the whole mesh to 768); the payload carries the
citation fields (book_id/title/author/section/chunk_id) AND the chunk text so a retrieval hit returns both the
source pointer and the passage. Qdrant collection `datasets_kindle_books`, Weaviate class `DatasetsKindleBooks`,
LanceDB table `books` (LanceDB defaults to vector_allow).
"""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks, build_vector_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.kindle_text_parse import KINDLE_TEXT_TABLES
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.streaming_producer import build_stream_produce_assets

KINDLE_CFG = DomainConfig(
    domain="kindle",
    repo="kindle",
    namespace="datasets_kindle",
    group_name="datasets_kindle",
    land_deps=("datasets_kindle_books_land",),
    # Base silver formats + Iceberg gold for the one books table — a Trino-queryable text corpus.
    parquet_allow=KINDLE_TEXT_TABLES, arrow_allow=KINDLE_TEXT_TABLES, avro_allow=KINDLE_TEXT_TABLES,
    iceberg_allow=KINDLE_TEXT_TABLES,
    # The chapter-aware chunks embed with bge-small (384) and fan out to Qdrant + Weaviate (+ LanceDB, which
    # defaults to vector_allow). `text` is embedded; the payload carries the citation fields AND the chunk text
    # so a hit returns both the source pointer (book/chapter/id) and the passage the KM query answers from.
    vector_allow={
        "books": {
            "text": ["text"],
            "payload": ["book_id", "title", "author", "section", "chunk_id", "text"],
        },
    },
    # All tabular/OLAP/graph/stream stores stay empty — a book chunk is text, not a relational/graph row.
)

(
    datasets_kindle_parquet, datasets_kindle_arrow, datasets_kindle_avro,
    datasets_kindle_lance, datasets_kindle_iceberg, datasets_kindle_commit,
) = build_transform_assets(KINDLE_CFG)

datasets_kindle_checks = build_asset_checks(KINDLE_CFG) + build_vector_checks(KINDLE_CFG)
datasets_kindle_store_assets = build_store_load_assets(KINDLE_CFG)
datasets_kindle_stream_assets = build_stream_produce_assets(KINDLE_CFG)
