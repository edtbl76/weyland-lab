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
VERSION = "0.4.0"

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

# Local model serving (B7): Ollama on weyland CT 102, OpenAI-compatible /v1 API.
# OLLAMA_MODEL is the default for /context/ask; callers may override per request.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.244:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")  # B4 panel-validated most-faithful pick
# Generation on CPU is slow (~25 tok/s) and qwen3 may emit a long thinking block — keep
# the timeout generous so legitimate answers aren't cut off mid-stream.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))


def validate_required_secrets() -> None:
    """Fail fast at startup if required secret-backed env vars are missing or empty.

    Passwords come from Kubernetes Secrets (weyland-postgres-secret, neo4j-secret)
    via secretKeyRef. If a Secret fails to mount, the env var is absent or empty —
    without this check the server starts with a blank password and fails later at
    connection time with a confusing error far from the real cause.

    Mirrors the fail-fast pattern already used in
    weyland-apisix/conf/routes-init.sh (missing admin key -> hard error).

    Raises:
        RuntimeError: if any required secret env var is missing or empty.
    """
    # Secret-backed values that must be present for the server to function.
    required = {
        "WEYLAND_DB_PASSWORD": PG_PASSWORD,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
    }
    # `not value` catches both the unset case and the empty-string case that a
    # secretKeyRef to a missing/blank key produces. Collect every missing var so
    # one error reports them all, rather than crashlooping one fix at a time.
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required secret env vars: "
            + ", ".join(missing)
            + ". These are supplied by Kubernetes Secrets "
            "(weyland-postgres-secret, neo4j-secret) via secretKeyRef — "
            "check that the Secrets exist in the 'weyland' namespace and are "
            "mounted by the deployment."
        )


# Fail loudly at import/startup, before the app builds connections.
validate_required_secrets()

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


class AskRequest(BaseModel):
    query: str
    backend: str = "pgvector"
    limit: int = 5
    # None -> fall back to OLLAMA_MODEL. Pass any model pulled on the Ollama host
    # (see GET /models) to override per request.
    model: str | None = None


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
    results = qdrant_client.query_points(
        collection_name="weyland_chunks",
        query=embedding,
        limit=limit,
    ).points
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


# --- Backend health helpers (shared by the per-backend endpoints and /status) ---
def _check_pgvector() -> dict:
    try:
        with psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER,
            password=PG_PASSWORD, connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _check_qdrant() -> dict:
    try:
        url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return {"status": "ok", "collections": data.get("result", {}).get("collections", [])}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _check_weaviate() -> dict:
    try:
        url = f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}/v1/.well-known/ready"
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _check_neo4j() -> dict:
    try:
        with neo4j_driver.session() as session:
            session.run("RETURN 1").consume()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _check_ollama() -> dict:
    """Reachability + model inventory of the Ollama endpoint (GET /v1/models is cheap)."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/models", timeout=5)
        resp.raise_for_status()
        models = [m["id"] for m in resp.json().get("data", [])]
        return {"status": "ok", "models": models}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# --- RAG generation helpers (retrieve -> ground -> generate via the local model) ---
RAG_SYSTEM_PROMPT = (
    "You are the Weyland lab assistant. Answer the question using ONLY the context "
    "chunks provided. If the context does not contain the answer, say so plainly rather "
    "than guessing. Cite the source name(s) you used."
)


def _build_context(chunks: list[dict]) -> str:
    """Render retrieved chunks into a numbered, source-tagged context block for the prompt."""
    return "\n\n".join(
        f"[{i + 1}] source: {c['source']} (chunk {c['chunk_index']})\n{c['content']}"
        for i, c in enumerate(chunks)
    )


def _ollama_chat(messages: list[dict], model: str) -> str:
    """Call the Ollama OpenAI-compatible chat endpoint and return the answer text.

    Engine-agnostic: the same call works against vLLM if a GPU is added later — only
    OLLAMA_BASE_URL changes.
    """
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/chat/completions",
        json={"model": model, "messages": messages, "stream": False},
        timeout=OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@app.get("/health")
def health():
    """Liveness — is the process up? Trivial by design; backs the livenessProbe."""
    return {"status": "ok", "service": "weyland-tool-server", "version": VERSION}


@app.get("/ready")
def ready():
    """Readiness — can we serve the core path? Gates on embed model + pgvector (the
    default backend) ONLY, so a single non-default backend being down does NOT pull the
    server out of rotation. Backs the readinessProbe (503 => NotReady)."""
    if embed_model is None:
        raise HTTPException(status_code=503, detail="embedding model not loaded")
    pg = _check_pgvector()
    if pg["status"] != "ok":
        raise HTTPException(status_code=503, detail=f"pgvector not ready: {pg.get('detail')}")
    return {"status": "ready"}


@app.get("/pgvector/health")
def pgvector_health():
    return {**_check_pgvector(), "pgvector_host": f"{PG_HOST}:{PG_PORT}"}


@app.get("/qdrant/health")
def qdrant_health():
    return {**_check_qdrant(), "qdrant_url": f"http://{QDRANT_HOST}:{QDRANT_PORT}"}


@app.get("/weaviate/health")
def weaviate_health():
    return {**_check_weaviate(), "weaviate_url": f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}"}


@app.get("/neo4j/health")
def neo4j_health():
    return {**_check_neo4j(), "neo4j_uri": NEO4J_URI}


@app.get("/ollama/health")
def ollama_health():
    return {**_check_ollama(), "ollama_url": OLLAMA_BASE_URL, "default_model": OLLAMA_MODEL}


@app.get("/status")
def status():
    """Consolidated health — server + model + all four backends in one call.
    overall='degraded' if any backend is down (the server itself stays live/ready)."""
    backends = {
        "pgvector": _check_pgvector(),
        "qdrant": _check_qdrant(),
        "weaviate": _check_weaviate(),
        "neo4j": _check_neo4j(),
    }
    llm = _check_ollama()
    healthy = all(b["status"] == "ok" for b in backends.values()) and llm["status"] == "ok"
    return {
        "service": "weyland-tool-server",
        "version": VERSION,
        "status": "ok" if healthy else "degraded",
        "model": {"name": MODEL_NAME, "loaded": embed_model is not None},
        "llm": {"endpoint": OLLAMA_BASE_URL, "default_model": OLLAMA_MODEL, **llm},
        "backends": backends,
    }


@app.post("/context/search")
def context_search(request: ContextSearchRequest, backend: str = Query(default="pgvector")):
    if backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{backend}'. Valid options: {sorted(VALID_BACKENDS)}",
        )
    results = SEARCH_FNS[backend](request.query, request.limit)
    return {"query": request.query, "results": results}


@app.get("/models")
def list_models():
    """Models available on the Ollama endpoint, for client-side selection in /context/ask."""
    check = _check_ollama()
    if check["status"] != "ok":
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {check.get('detail')}")
    return {"default": OLLAMA_MODEL, "available": check["models"]}


@app.post("/context/ask")
def context_ask(request: AskRequest):
    """RAG: retrieve top-k chunks from a backend, then have the local model synthesize a
    grounded answer. `model` is selectable per request (defaults to OLLAMA_MODEL)."""
    if request.backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{request.backend}'. Valid options: {sorted(VALID_BACKENDS)}",
        )
    model = request.model or OLLAMA_MODEL
    chunks = SEARCH_FNS[request.backend](request.query, request.limit)
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{_build_context(chunks)}\n\nQuestion: {request.query}"},
    ]
    try:
        answer = _ollama_chat(messages, model)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed ({model}): {e}")
    return {
        "query": request.query,
        "backend": request.backend,
        "model": model,
        "answer": answer,
        "sources": chunks,
    }


def _launch_dagster_job(job_name: str) -> dict:
    """Fire a Dagster job via GraphQL launchRun. Shared by /pipeline/trigger and /evals/*."""
    mutation = {
        "query": (
            "mutation Launch($job: String!) {"
            "launchRun(executionParams: {selector: {repositoryLocationName: \"weyland_pipeline\", "
            "repositoryName: \"__repository__\", jobName: $job}, "
            "mode: \"default\", executionMetadata: {tags: []}}) {"
            "__typename ... on LaunchRunSuccess { run { runId } } ... on PythonError { message }"
            "}}"
        ),
        "variables": {"job": job_name},
    }
    resp = httpx.post(f"{DAGSTER_URL}/graphql", json=mutation, timeout=10)
    resp.raise_for_status()
    result = resp.json().get("data", {}).get("launchRun", {})
    if result.get("__typename") != "LaunchRunSuccess":
        raise HTTPException(status_code=502, detail=result.get("message", "Dagster launch failed"))
    return {"status": "ok", "run_id": result["run"]["runId"], "job_name": job_name}


@app.post("/pipeline/trigger")
def pipeline_trigger(request: PipelineTriggerRequest):
    return _launch_dagster_job(request.job_name)


# --- B4 eval endpoints (single-path eval + leaderboard; see docs/b4-eval-runbook.md) ---
def _eval_pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD, connect_timeout=5
    )


@app.post("/evals/run")
def evals_run():
    """Single-path eval: generate a question set + run the model matrix. Then POST /evals/score."""
    return _launch_dagster_job("weyland_eval_job")


@app.post("/evals/score")
def evals_score():
    """Judge-panel scoring of the latest completed matrix run."""
    return _launch_dagster_job("weyland_eval_score_job")


@app.get("/evals/runs")
def evals_runs():
    """List recent eval runs."""
    with _eval_pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, created_at, status, models, question_count, notes "
                "FROM eval_runs ORDER BY id DESC LIMIT 20"
            )
            rows = cur.fetchall()
    return {
        "runs": [
            {
                "id": r[0],
                "created_at": r[1].isoformat(),
                "status": r[2],
                "models": r[3],
                "question_count": r[4],
                "notes": r[5],
            }
            for r in rows
        ]
    }


@app.get("/evals/leaderboard")
def evals_leaderboard(run_id: int | None = Query(default=None)):
    """Panel-averaged leaderboard for a run (default: the latest scored run)."""
    with _eval_pg_conn() as conn:
        with conn.cursor() as cur:
            if run_id is None:
                cur.execute("SELECT id FROM eval_runs WHERE status = 'scored' ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="no scored eval run found")
                run_id = row[0]
            cur.execute(
                """
                SELECT model,
                       round(avg(score) FILTER (WHERE metric='faithfulness')::numeric, 3),
                       round(avg(score) FILTER (WHERE metric='answer_relevancy')::numeric, 3),
                       round(avg(score) FILTER (WHERE metric='context_relevancy')::numeric, 3),
                       count(DISTINCT judge)
                FROM eval_results r JOIN eval_scores s ON s.result_id = r.id
                WHERE r.run_id = %s
                GROUP BY model
                ORDER BY 2 DESC NULLS LAST
                """,
                (run_id,),
            )
            rows = cur.fetchall()
    return {
        "run_id": run_id,
        "leaderboard": [
            {
                "model": r[0],
                "faithfulness": float(r[1]) if r[1] is not None else None,
                "answer_relevancy": float(r[2]) if r[2] is not None else None,
                "context_relevancy": float(r[3]) if r[3] is not None else None,
                "judges": r[4],
            }
            for r in rows
        ],
    }
