"""weyland-agent — agentic RAG on LangGraph + LlamaIndex + MLflow tracing (B70 Part 3).

The sibling service to the tool-server: a self-reflective retrieve → grade → reflect/re-retrieve → answer loop over
the 4 vector backends, more capable than the single-shot `/context/ask`. Every step is captured as an MLflow Trace
(dual autolog). Guards the outer query + final answer via the shared weyland-guard service (fail-open)."""
import os
import time
import uuid
from contextlib import asynccontextmanager

import mlflow
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

import retrievers
from graph import build_graph
from guard import guard

VERSION = "0.1.0"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "agentic-rag")

_REQS = Counter("agent_requests_total", "Agent /ask requests", ["outcome"])
_ATTEMPTS = Histogram("agent_attempts", "Retrieval attempts per query", buckets=[1, 2, 3, 4, 5])
_LATENCY = Histogram("agent_request_seconds", "End-to-end /agent/ask latency (s)")

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    retrievers.init()                       # loads bge in-process + opens qdrant/weaviate/neo4j clients
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        mlflow.langchain.autolog()          # graph + LLM spans
        mlflow.llama_index.autolog()        # retrieval spans → one unified Trace per /agent/ask
    except Exception as exc:                # tracing is advisory — never block startup
        print(f"[mlflow] tracing disabled: {exc}", flush=True)
    global _graph
    _graph = build_graph()
    yield
    retrievers.close()


app = FastAPI(title="Weyland Agent", lifespan=lifespan)


def _actor(x_forwarded_consumer: str | None = Header(default=None)) -> str | None:
    return x_forwarded_consumer


class AskRequest(BaseModel):
    query: str
    backend: str = "pgvector"
    max_attempts: int = 2


@app.post("/agent/ask")
def agent_ask(req: AskRequest, actor: str | None = Depends(_actor)):
    if req.backend not in retrievers.VALID_BACKENDS:
        raise HTTPException(400, f"unknown backend '{req.backend}'. Valid: {sorted(retrievers.VALID_BACKENDS)}")
    request_id = str(uuid.uuid4())
    if guard("input", request_id, {"query": req.query}, actor):
        _REQS.labels("blocked").inc()
        raise HTTPException(403, "blocked by input guard")

    state = {"query": req.query, "original_query": req.query, "backend": req.backend,
             "chunks": [], "grade": "", "attempts": 0, "max_attempts": req.max_attempts,
             "answer": "", "backend_history": [req.backend]}
    t0 = time.monotonic()
    try:
        result = _graph.invoke(state)
    except Exception as exc:
        _REQS.labels("error").inc()
        raise HTTPException(502, f"agent run failed: {exc}")
    _LATENCY.observe(time.monotonic() - t0)
    _ATTEMPTS.observe(result["attempts"] + 1)

    if guard("output", request_id, {"answer": result["answer"], "sources": result["chunks"]}, actor):
        _REQS.labels("blocked").inc()
        raise HTTPException(403, "blocked by output guard")
    _REQS.labels("ok").inc()
    return {"query": req.query, "answer": result["answer"], "sources": result["chunks"],
            "attempts": result["attempts"] + 1, "backend_used": result["backend"],
            "backend_history": result["backend_history"]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "weyland-agent", "version": VERSION}


@app.get("/ready")
def ready():
    if not retrievers.ready() or _graph is None:
        return JSONResponse(status_code=503, content={"status": "loading"})
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
