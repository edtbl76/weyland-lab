"""Custom LlamaIndex retrievers over the existing RAG collections (B70 Part 3).

Native LlamaIndex vector stores DON'T fit these collections — the B-RAG-STREAM indexer stores chunk text under
`content` (not LlamaIndex's `text`) and writes no `_node_content` blob, so `PGVectorStore`/`QdrantVectorStore` can't
reconstruct nodes (pgvector is also a two-table join). So we wrap the tool-server's *proven* per-backend queries in
thin `BaseRetriever`s — the LangGraph nodes get a standard retriever interface and LlamaIndex autolog captures the
span. Query embedding is IN-PROCESS bge-base (768, B74) — the SAME model the tool-server uses for query embedding and the SAME
the collections were built with (guaranteed vector-space parity)."""
import os

import psycopg2
import weaviate
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from weaviate.classes.query import MetadataQuery

MODEL_NAME = "BAAI/bge-base-en-v1.5"   # B74: 768-dim — MUST match the collections + the tool-server query embedder
VALID_BACKENDS = {"pgvector", "qdrant", "weaviate", "neo4j"}

PG_HOST = os.getenv("WEYLAND_DB_HOST", "weyland-postgres.weyland.svc.cluster.local")
PG_PORT = int(os.getenv("WEYLAND_DB_PORT", "5432"))
PG_DB = os.getenv("WEYLAND_DB_NAME", "weyland")
PG_USER = os.getenv("WEYLAND_DB_USER", "weyland")
PG_PASSWORD = os.getenv("WEYLAND_DB_PASSWORD", "")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant.weyland.svc.cluster.local")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "weaviate.weyland.svc.cluster.local")
WEAVIATE_PORT = int(os.getenv("WEAVIATE_PORT", "8080"))
WEAVIATE_GRPC_PORT = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j.weyland.svc.cluster.local:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

_embed: HuggingFaceEmbedding | None = None
_qdrant: QdrantClient | None = None
_weaviate = None
_neo4j = None


def init() -> None:
    """Load the embedding model + open the persistent clients. Called once at app startup (lifespan)."""
    global _embed, _qdrant, _weaviate, _neo4j
    _embed = HuggingFaceEmbedding(model_name=MODEL_NAME)
    _qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    _weaviate = weaviate.connect_to_custom(
        http_host=WEAVIATE_HOST, http_port=WEAVIATE_PORT, http_secure=False,
        grpc_host=WEAVIATE_HOST, grpc_port=WEAVIATE_GRPC_PORT, grpc_secure=False,
    )
    _neo4j = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def close() -> None:
    if _weaviate:
        _weaviate.close()
    if _neo4j:
        _neo4j.close()


def ready() -> bool:
    return _embed is not None


def _to_vector(values) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


# --- per-backend raw queries (lifted verbatim from weyland-tool-server main.py) -------------------
def _search_pgvector(query: str, limit: int) -> list[dict]:
    vec = _to_vector(_embed.get_text_embedding(query))
    with psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT d.name, c.chunk_index, 1 - (c.embedding <=> %s::vector) AS score, c.content "
                "FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id "
                "WHERE c.embedding IS NOT NULL ORDER BY c.embedding <=> %s::vector LIMIT %s",
                (vec, vec, limit),
            )
            return [{"source": n, "chunk_index": ci, "similarity": float(s), "content": ct}
                    for n, ci, s, ct in cur.fetchall()]


def _search_qdrant(query: str, limit: int) -> list[dict]:
    pts = _qdrant.query_points(collection_name="weyland_chunks",
                               query=_embed.get_text_embedding(query), limit=limit).points
    return [{"source": r.payload.get("source_name", ""), "chunk_index": r.payload.get("chunk_index", 0),
             "similarity": float(r.score), "content": r.payload.get("content", "")} for r in pts]


def _search_weaviate(query: str, limit: int) -> list[dict]:
    col = _weaviate.collections.get("WeylandChunk")
    res = col.query.near_vector(near_vector=_embed.get_text_embedding(query), limit=limit,
                                return_metadata=MetadataQuery(distance=True))
    return [{"source": o.properties.get("source_path", "").split("/")[-1].replace(".md", ""),
             "chunk_index": o.properties.get("chunk_index", 0),
             "similarity": float(1 - (o.metadata.distance or 0)),
             "content": o.properties.get("content", "")} for o in res.objects]


def _search_neo4j(query: str, limit: int) -> list[dict]:
    with _neo4j.session() as s:
        res = s.run(
            "CALL db.index.vector.queryNodes('weyland_chunk_embedding', $limit, $embedding) "
            "YIELD node, score MATCH (node)-[:BELONGS_TO]->(d:Document) "
            "RETURN node.content AS content, node.chunk_index AS chunk_index, d.source_name AS source_name, score",
            limit=limit, embedding=_embed.get_text_embedding(query),
        )
        return [{"source": r["source_name"] or "", "chunk_index": r["chunk_index"] or 0,
                 "similarity": float(r["score"]), "content": r["content"] or ""} for r in res]


_SEARCH = {"pgvector": _search_pgvector, "qdrant": _search_qdrant,
           "weaviate": _search_weaviate, "neo4j": _search_neo4j}


class WeylandRetriever(BaseRetriever):
    """LlamaIndex retriever over one backend — wraps the raw query so the graph gets a standard interface."""

    def __init__(self, backend: str, limit: int = 5):
        super().__init__()
        self.backend = backend
        self.limit = limit

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        chunks = _SEARCH[self.backend](query_bundle.query_str, self.limit)
        return [NodeWithScore(
            node=TextNode(text=c["content"], metadata={"source": c["source"], "chunk_index": c["chunk_index"]}),
            score=c["similarity"]) for c in chunks]
