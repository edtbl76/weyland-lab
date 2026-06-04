import os
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

import json
import urllib.request

app = FastAPI(title="Weyland Tool Server")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
QDRANT_URL = os.getenv("WEYLAND_QDRANT_URL", "http://localhost:6333")
model = SentenceTransformer(MODEL_NAME)


class ContextSearchRequest(BaseModel):
    query: str
    limit: int = 5


class ContextSourceStateRequest(BaseModel):
    source_path: str


class ContextIngestChunk(BaseModel):
    name: str
    source_type: str
    source_path: str
    chunk_index: int
    chunk_title: str | None = None
    content: str
    metadata: dict[str, Any] = {}


class ContextIngestRequest(BaseModel):
    name: str
    source_type: str
    source_path: str
    content_hash: str | None = None
    chunks: list[ContextIngestChunk]


def get_connection():
    return psycopg2.connect(
        host=os.getenv("WEYLAND_DB_HOST", "localhost"),
        port=int(os.getenv("WEYLAND_DB_PORT", "5432")),
        dbname=os.getenv("WEYLAND_DB_NAME", "weyland"),
        user=os.getenv("WEYLAND_DB_USER", "weyland"),
        password=os.getenv("WEYLAND_DB_PASSWORD", "weyland_dev_password"),
    )


def to_vector(values: Any) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "weyland-tool-server",
    }

@app.get("/qdrant/health")
def qdrant_health():
    url = f"{QDRANT_URL}/collections"

    with urllib.request.urlopen(url, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))

    return {
        "status": "ok",
        "qdrant_url": QDRANT_URL,
        "collections": data.get("result", {}).get("collections", []),
    }

@app.post("/context/source-state")
def context_source_state(request: ContextSourceStateRequest):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  name,
                  source_type,
                  source_path,
                  content_hash,
                  updated_at
                FROM rag_documents
                WHERE source_path = %s;
                """,
                (request.source_path,),
            )

            row = cur.fetchone()

    if row is None:
        return {
            "exists": False,
            "source_path": request.source_path,
            "content_hash": None,
        }

    name, source_type, source_path, content_hash, updated_at = row

    return {
        "exists": True,
        "name": name,
        "source_type": source_type,
        "source_path": source_path,
        "content_hash": content_hash,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@app.post("/context/search")
def context_search(request: ContextSearchRequest):
    embedding = model.encode(request.query, normalize_embeddings=True)
    vector = to_vector(embedding)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  d.name,
                  c.chunk_index,
                  1 - (c.embedding <=> %s::vector) AS similarity,
                  c.content
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s;
                """,
                (vector, vector, request.limit),
            )

            results = []
            for name, chunk_index, similarity, content in cur.fetchall():
                results.append({
                    "source": name,
                    "chunk_index": chunk_index,
                    "similarity": float(similarity),
                    "content": content,
                })

    return {
        "query": request.query,
        "results": results,
    }


@app.post("/context/ingest")
def context_ingest(request: ContextIngestRequest):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_documents
                  (name, source_type, source_path, content_hash, metadata)
                VALUES
                  (%s, %s, %s, %s, %s)
                ON CONFLICT (source_path)
                DO UPDATE SET
                  name = EXCLUDED.name,
                  source_type = EXCLUDED.source_type,
                  content_hash = EXCLUDED.content_hash,
                  metadata = EXCLUDED.metadata,
                  updated_at = now()
                RETURNING id;
                """,
                (
                    request.name,
                    request.source_type,
                    request.source_path,
                    request.content_hash,
                    psycopg2.extras.Json({}),
                ),
            )

            document_id = cur.fetchone()[0]

            cur.execute(
                "DELETE FROM rag_chunks WHERE document_id = %s;",
                (document_id,),
            )

            for chunk in request.chunks:
                embedding = model.encode(chunk.content, normalize_embeddings=True)
                vector = to_vector(embedding)

                metadata = dict(chunk.metadata or {})
                if chunk.chunk_title:
                    metadata["title"] = chunk.chunk_title

                cur.execute(
                    """
                    INSERT INTO rag_chunks
                      (document_id, chunk_index, content, embedding, metadata)
                    VALUES
                      (%s, %s, %s, %s::vector, %s);
                    """,
                    (
                        document_id,
                        chunk.chunk_index,
                        chunk.content,
                        vector,
                        psycopg2.extras.Json(metadata),
                    ),
                )

    return {
        "status": "ok",
        "document": request.name,
        "source_path": request.source_path,
        "content_hash": request.content_hash,
        "chunks_ingested": len(request.chunks),
    }
