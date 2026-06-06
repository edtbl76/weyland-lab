import json
import os
import urllib.request
from contextlib import asynccontextmanager

import httpx
import psycopg2
import weaviate
from fastapi import FastAPI, HTTPException, Query
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from neo4j import GraphDatabase
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from weaviate.classes.query import MetadataQuery

MODEL_NAME = "BAAI/bge-small-en-v1.5"

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

DAGSTER_URL = os.getenv("DAGSTER_URL", "http://dagster-webserver.weyland.svc.cluster.local:3000")

VALID_BACKENDS = {"pgvector", "qdrant", "weaviate", "neo4j"}

embed_model: HuggingFaceEmbedding | None = None
qdrant_client: QdrantClient | None = None
weaviate_client: weaviate.WeaviateClient | None = None
neo4j_driver = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embed_model, qdrant_client, weaviate_client, neo4j_driver
    embed_model = HuggingFaceEmbedding(model_name=MODEL_NAME)
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    weaviate_client = weaviate.connect_to_custom(
        http_host=WEAVIATE_HOST,
        http_port=WEAVIATE_PORT,
        http_secure=False,
        grpc_host=WEAVIATE_HOST,
        grpc_port=WEAVIATE_GRPC_PORT,
        grpc_secure=False,
    )
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield
    if weaviate_client:
        weaviate_client.close()
    if neo4j_driver:
        neo4j_driver.close()


app = FastAPI(title="Weyland Tool Server", lifespan=lifespan)


class ContextSearchRequest(BaseModel):
    query: str
    limit: int = 5


class PipelineTriggerRequest(BaseModel):
    job_name: str = Field(default="weyland_ingestion_job", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


def _to_vector(values) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


def _search_pgvector(query: str, limit: int) -> list[dict]:
    embedding = embed_model.get_text_embedding(query)
    vector = _to_vector(embedding)
    with psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.name, c.chunk_index, 1 - (c.embedding <=> %s::vector) AS score, c.content
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (vector, vector, limit),
            )
            return [
                {"source": name, "chunk_index": ci, "similarity": float(score), "content": content}
                for name, ci, score, content in cur.fetchall()
            ]


def _search_qdrant(query: str, limit: int) -> list[dict]:
    embedding = embed_model.get_text_embedding(query)
    results = qdrant_client.search(
        collection_name="weyland_chunks",
        query_vector=embedding,
        limit=limit,
    )
    return [
        {
            "source": r.payload.get("source_name", ""),
            "chunk_index": r.payload.get("chunk_index", 0),
            "similarity": float(r.score),
            "content": r.payload.get("content", ""),
        }
        for r in results
    ]


def _search_weaviate(query: str, limit: int) -> list[dict]:
    embedding = embed_model.get_text_embedding(query)
    chunks_col = weaviate_client.collections.get("WeylandChunk")
    results = chunks_col.query.near_vector(
        near_vector=embedding,
        limit=limit,
        return_metadata=MetadataQuery(distance=True),
    )
    return [
        {
            "source": o.properties.get("source_path", "").split("/")[-1].replace(".md", ""),
            "chunk_index": o.properties.get("chunk_index", 0),
            "similarity": float(1 - (o.metadata.distance or 0)),
            "content": o.properties.get("content", ""),
        }
        for o in results.objects
    ]


def _search_neo4j(query: str, limit: int) -> list[dict]:
    embedding = embed_model.get_text_embedding(query)
    with neo4j_driver.session() as session:
        result = session.run(
            """
            CALL db.index.vector.queryNodes('weyland_chunk_embedding', $limit, $embedding)
            YIELD node, score
            MATCH (node)-[:BELONGS_TO]->(d:Document)
            RETURN node.content AS content, node.chunk_index AS chunk_index, d.source_name AS source_name, score
            """,
            limit=limit,
            embedding=embedding,
        )
        return [
            {
                "source": r["source_name"] or "",
                "chunk_index": r["chunk_index"] or 0,
                "similarity": float(r["score"]),
                "content": r["content"] or "",
            }
            for r in result
        ]


SEARCH_FNS = {
    "pgvector": _search_pgvector,
    "qdrant": _search_qdrant,
    "weaviate": _search_weaviate,
    "neo4j": _search_neo4j,
}


@app.get("/health")
def health():
    return {"status": "ok", "service": "weyland-tool-server"}


@app.get("/qdrant/health")
def qdrant_health():
    url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    return {
        "status": "ok",
        "qdrant_url": f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        "collections": data.get("result", {}).get("collections", []),
    }


@app.get("/weaviate/health")
def weaviate_health():
    url = f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}/v1/.well-known/ready"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        return {"status": "ok", "weaviate_url": f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/neo4j/health")
def neo4j_health():
    try:
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        return {"status": "ok", "neo4j_uri": NEO4J_URI}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/context/search")
def context_search(request: ContextSearchRequest, backend: str = Query(default="pgvector")):
    if backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{backend}'. Valid options: {sorted(VALID_BACKENDS)}",
        )
    results = SEARCH_FNS[backend](request.query, request.limit)
    return {"query": request.query, "results": results}


@app.post("/pipeline/trigger")
def pipeline_trigger(request: PipelineTriggerRequest):
    mutation = {
        "query": (
            "mutation Launch($job: String!) {"
            "launchRun(executionParams: {selector: {repositoryLocationName: \"weyland_pipeline\", "
            "repositoryName: \"__repository__\", jobName: $job}, "
            "mode: \"default\", executionMetadata: {tags: []}}) {"
            "__typename ... on LaunchRunSuccess { run { runId } } ... on PythonError { message }"
            "}}"
        ),
        "variables": {"job": request.job_name},
    }
    resp = httpx.post(f"{DAGSTER_URL}/graphql", json=mutation, timeout=10)
    resp.raise_for_status()
    result = resp.json().get("data", {}).get("launchRun", {})
    if result.get("__typename") != "LaunchRunSuccess":
        raise HTTPException(status_code=502, detail=result.get("message", "Dagster launch failed"))
    return {"status": "ok", "run_id": result["run"]["runId"], "job_name": request.job_name}
