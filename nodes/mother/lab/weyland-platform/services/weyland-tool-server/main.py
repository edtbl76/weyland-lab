import json
import os
import sys
import urllib.request
import uuid
from contextlib import asynccontextmanager, contextmanager
from typing import Literal

import httpx
import psycopg2
import sentry_sdk
import weaviate
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import RouteMap, MCPType
from neo4j import GraphDatabase
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel
from qdrant_client import QdrantClient
from weaviate.classes.query import MetadataQuery

from grkit.verdict import Decision, Hook, Verdict
from prompts import load_prompt, loaded_version

# B51 — error tracking → GlitchTip (Sentry SDK). DSN from env; empty DSN = disabled (no-op), so the image
# still runs standalone for dev. FastAPI/Starlette are auto-instrumented by the SDK on init.
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    environment=os.getenv("SENTRY_ENVIRONMENT", "weyland"),
    traces_sample_rate=0.0,
    send_default_pii=False,
)

MODEL_NAME = "BAAI/bge-base-en-v1.5"   # B74: 768-dim — MUST match the ingest embedder (query & index dims must agree)
MODEL_DIR = os.environ.get("BGE_ONNX_DIR", "/app/bge_onnx")   # ONNX export baked at build time (see Dockerfile)


class OnnxBge:
    """bge-base-en-v1.5 query embedder on raw ONNX Runtime (U13). CLS pooling + L2 normalize —
    byte-equivalent to sentence-transformers/HuggingFaceEmbedding (verified cosine 1.0 vs ST, so the
    hydrated Qdrant/Weaviate/Neo4j vectors stay valid; NO re-hydration). Runtime deps are onnxruntime +
    tokenizers + numpy ONLY — torch/transformers/sentence-transformers are gone (~1.2 GB dropped). The
    ONNX model + tokenizer.json are exported in the Dockerfile's builder stage."""

    def __init__(self, model_dir: str = MODEL_DIR):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self._sess = ort.InferenceSession(f"{model_dir}/model.onnx", providers=["CPUExecutionProvider"])
        self._tok = Tokenizer.from_file(f"{model_dir}/tokenizer.json")
        self._tok.enable_truncation(max_length=512)
        self._names = [i.name for i in self._sess.get_inputs()]

    def get_text_embedding(self, text: str) -> list[float]:
        import numpy as np
        e = self._tok.encode(text)
        avail = {"input_ids": e.ids, "attention_mask": e.attention_mask, "token_type_ids": e.type_ids}
        feed = {n: np.array([avail[n]], dtype=np.int64) for n in self._names}
        cls = self._sess.run(None, feed)[0][0, 0]     # (1,seq,768) -> CLS token
        return (cls / np.linalg.norm(cls)).astype(np.float32).tolist()


VERSION = "0.7.0"  # B100 Phase 2 — RAG system prompt from the MLflow Prompt Registry (fail-safe, TTL-cached)

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
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")  # B4 panel-validated most-faithful pick
# Generation on CPU is slow (~25 tok/s) and qwen3 may emit a long thinking block — keep
# the timeout generous so legitimate answers aren't cut off mid-stream.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))
# The bearer token rogueone's Ollama front door asks remote callers for (B211, 2026-10-22; secret ollama-proxy-token).
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")


def _ollama_headers() -> dict:
    return {"Authorization": f"Bearer {OLLAMA_API_KEY}"}


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

embed_model: OnnxBge | None = None
qdrant_client: QdrantClient | None = None
weaviate_client: weaviate.WeaviateClient | None = None
neo4j_driver = None

# --- B14 guardrails → shared weyland-guard service (B70 Part 2) ------------------
# The validator MODELS moved OUT to weyland-guard; the tool-server now POSTs each hook to it over HTTP. The service
# owns the SHADOW/FLAG/BLOCK modes and answers fast for shadow (records the verdict async), so this is an in-cluster
# round-trip, not model-inference latency. INPUT/OUTPUT FAIL OPEN (a guard outage degrades to "not guarded", never
# "no answer"); ACT FAILS CLOSED (an outage refuses the act) — see _guard_failed (B207).
GUARD_BASE_URL = os.getenv("GUARD_BASE_URL", "http://weyland-guard.weyland.svc.cluster.local:8080")
GUARD_TIMEOUT = float(os.getenv("GUARD_TIMEOUT", "10"))
_GUARD_PATHS = {Hook.INPUT: "/guard/input", Hook.OUTPUT: "/guard/output", Hook.ACT: "/guard/act"}

# B207 DoD (2026-10-14): failing open on content and closed on authority is only safe when it is LOUD. Every guard call
# that got no usable answer is counted here; the GuardCallsFailing alert reads it (k8s/weyland-tool-server.yaml).
# input/output failures mean answers went out unguarded; act failures mean acts were refused, including a mesh denial
# ("RBAC: access denied" is not JSON, so it counts as bad_response).
GUARD_FAILURES = Counter("tool_server_guard_failures_total",
                         "Guard calls that got no usable answer, by hook and cause (content fails open, act fails closed)",
                         ["hook", "cause"])
# Export every hook x cause series at 0 from start-up (2026-10-21, DoD re-audit). GuardCallsFailing alerts on
# increase(...[10m]) > 0, and a labelled series that only appears with its first failure starts AT 1, so increase()
# sees nothing and the first failure — the one that matters on the act hook — would never page.
GUARD_FAILURE_CAUSES = ("timeout", "connection", "bad_response")
for _hook in _GUARD_PATHS:
    for _cause in GUARD_FAILURE_CAUSES:
        GUARD_FAILURES.labels(_hook.value, _cause)


def _actor(x_forwarded_consumer: str | None = Header(default=None)) -> str | None:
    """Caller identity for the audit, taken ONLY from the gateway's trusted header
    (X-Forwarded-Consumer, injected after the gateway authenticates a consumer — B17+B19). None until a
    gateway fronts the surface. We deliberately never read a client-supplied identity claim (anti-spoofing)."""
    return x_forwarded_consumer


def _guard_failed(hook: Hook, cause: str) -> Verdict | None:
    """What a guard failure means. INPUT/OUTPUT (content) FAIL OPEN: None = allow, so a guard outage never takes an
    answer offline. ACT (authority) FAILS CLOSED (B207, 2026-10-13): a guard that is down must not mean "anyone may
    act", so the act is refused with a verdict naming the cause."""
    GUARD_FAILURES.labels(hook.value, cause).inc()
    print(f"[guard] {hook.value} guard failed ({cause}) — {'refusing the act' if hook == Hook.ACT else 'allowing'}",
          flush=True)
    if hook == Hook.ACT:
        return Verdict("guard-unavailable", Decision.BLOCK, None, f"guard unavailable ({cause}): action refused", 0)
    return None


def _guard(hook: Hook, request_id: str, payload: dict, actor: str | None = None):
    """POST the hook to the shared weyland-guard service. Returns a BLOCK Verdict if the guard blocked (enforcing
    mode), or if the guard could not answer on the ACT hook; else None. Content hooks fail OPEN, the act hook fails
    CLOSED (see _guard_failed). The guard service owns the modes and answers fast for SHADOW (records the verdict
    async), so this is just an in-cluster round-trip, not model-inference latency. `payload` already carries the
    per-hook keys the guard expects (input=query, output=answer+sources, act=tool+params)."""
    body = {"request_id": request_id, "actor": actor, **payload}
    try:
        resp = httpx.post(f"{GUARD_BASE_URL}{_GUARD_PATHS[hook]}", json=body, timeout=GUARD_TIMEOUT)
        data = resp.json()
    except httpx.TimeoutException:
        return _guard_failed(hook, "timeout")
    except httpx.TransportError:
        return _guard_failed(hook, "connection")
    except Exception:
        return _guard_failed(hook, "bad_response")
    decision = data.get("decision") if isinstance(data, dict) else None
    if decision == "block":
        v = data.get("verdict") or {}
        return Verdict(v.get("validator", "guard"), Decision.BLOCK, v.get("score"), v.get("reason", ""), 0)
    if decision != "allow":
        return _guard_failed(hook, "bad_response")
    return None


def _guard_act(request_id: str, tool: str, actor: str | None, params: dict | None = None) -> None:
    """The act gate, ENFORCED: raise 403 before anything launches when the guard refuses the act. Until B207 the act
    endpoints called _guard and discarded its answer, so policy.gate's blocks were recorded and ignored."""
    payload = {"tool": tool, **({"params": params} if params is not None else {})}
    blocked = _guard(Hook.ACT, request_id, payload, actor)
    if blocked:
        raise HTTPException(status_code=403, detail=f"blocked by {blocked.validator}: {blocked.reason}")


# B100 Phase 1 — MLflow tracing for the RAG path. `/context/ask` generates via a raw httpx call to Ollama (not a
# LangChain/OpenAI client), so autolog can't see it — we emit manual spans. FAIL-SAFE: any tracing error degrades to
# a no-op, exactly like the guard is fail-open — observability must never take an answer offline.
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "tool-server-rag")
_tracing_enabled = False
_lf = None   # B103 — Langfuse client for prompt-linked RAG tracing (alongside MLflow)


def _init_tracing() -> None:
    global _tracing_enabled, _lf
    if not MLFLOW_TRACKING_URI:
        print("[mlflow] no MLFLOW_TRACKING_URI — RAG tracing disabled", flush=True)
    else:
        try:
            import mlflow
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment(MLFLOW_EXPERIMENT)
            _tracing_enabled = True
            print(f"[mlflow] RAG tracing enabled -> {MLFLOW_EXPERIMENT}", flush=True)
        except Exception as exc:
            print(f"[mlflow] tracing disabled: {exc}", flush=True)
    # B103 prompt federation — ALSO trace the RAG generation to Langfuse (alongside MLflow), linking the prompt
    # version so the Langfuse trace shows which rag_system version produced the answer. Fail-safe: never blocks a request.
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            from langfuse import Langfuse
            _lf = Langfuse()   # reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST from env
            print("[langfuse] RAG prompt-linked tracing enabled", flush=True)
        except Exception as exc:
            print(f"[langfuse] tracing disabled: {exc}", flush=True)


@contextmanager
def _span(name: str, span_type: str = "UNKNOWN"):
    """A fail-safe MLflow span: yields the span (or None if tracing is off/broken). A tracing failure never
    interrupts the request, and an exception from the body propagates cleanly. Setup and yield are separated (like
    _lf_generation) so a broken SDK call — OR an exception thrown into the span from the body — can't double-yield
    (`RuntimeError: generator didn't stop after throw()`) and mask the real error."""
    if not _tracing_enabled:
        yield None
        return
    span_cm = span = None
    try:
        import mlflow
        span_cm = mlflow.start_span(name=name, span_type=span_type)
        span = span_cm.__enter__()
    except Exception:
        span_cm = span = None
    try:
        yield span
    finally:
        if span_cm is not None:
            try:
                span_cm.__exit__(*sys.exc_info())   # records the body's exception on the span, then closes it
            except Exception:
                pass


@contextmanager
def _lf_generation(name: str, model: str, input_messages, prompt_name: str,
                   session_id: str | None = None, user_id: str | None = None, enabled: bool = True):
    """B103 — a fail-safe Langfuse generation LINKED to the Langfuse prompt version (SDK v4), running ALONGSIDE the
    MLflow span. Yields a generation handle (call `.update(output=...)`), or None if Langfuse is off/broken. A tracing
    failure never interrupts the request; flushes on exit so the trace lands on this request/response server. Setup and
    yield are separated so a broken SDK call can't double-yield. `session_id` groups related asks into one session."""
    if _lf is None or not enabled:
        yield None
        return
    prop_cm = gen_cm = gen = None
    try:
        prompt = None
        try:
            prompt = _lf.get_prompt(prompt_name, type="chat")   # object carries the version -> links the trace
        except Exception:
            pass
        if session_id or user_id:                        # session grouping — propagate_attributes (langfuse v4), set BEFORE the obs
            try:
                from langfuse import propagate_attributes
                prop_cm = propagate_attributes(session_id=session_id, user_id=user_id)
                prop_cm.__enter__()
            except Exception:
                prop_cm = None
        gen_cm = _lf.start_as_current_observation(as_type="generation", name=name, model=model,
                                                  input=input_messages, prompt=prompt)
        gen = gen_cm.__enter__()
    except Exception:
        gen_cm = gen = None
    try:
        yield gen
    finally:
        try:
            if gen_cm is not None:
                gen_cm.__exit__(None, None, None)
            if prop_cm is not None:
                prop_cm.__exit__(None, None, None)
            _lf.flush()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embed_model, qdrant_client, weaviate_client, neo4j_driver
    embed_model = OnnxBge(MODEL_DIR)
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
    _init_tracing()   # B100 Phase 1 — RAG tracing (fail-safe)
    # B111 Option C: run the FastMCP streamable-HTTP session managers for the /mcp and /mcp-act
    # sub-apps INSIDE the app lifespan. Starlette does NOT auto-run a mounted sub-app's lifespan,
    # and the session manager MUST be running or the transport hangs on request.body() (the exact
    # fastapi-mcp 0.4.0 failure this replaces). Forward-ref'd globals exist by call time (module
    # fully imported before uvicorn starts the lifespan).
    async with _mcp_read_app.lifespan(app), _mcp_act_app.lifespan(app):
        yield
    if weaviate_client:
        weaviate_client.close()
    if neo4j_driver:
        neo4j_driver.close()


app = FastAPI(title="Weyland Tool Server", lifespan=lifespan)

_ENCODED_SEPARATORS = (b"%2f", b"%5c")   # "/" and "\\" percent-encoded, compared lower-cased


@app.middleware("http")
async def _refuse_encoded_separators(request, call_next):
    """Refuse a path carrying an ENCODED separator before routing (B207, 2026-10-13). The act paths are protected by
    an Istio DENY that matches exact paths; the mesh does not decode %2F, uvicorn does — so `/pipeline%2Ftrigger`
    from any pod reached the act endpoint past the DENY (observed live). No route here needs one, so refuse them all."""
    raw = (request.scope.get("raw_path") or request.url.path.encode()).lower()
    if any(sep in raw for sep in _ENCODED_SEPARATORS):
        return JSONResponse(status_code=400, content={"detail": "encoded path separators are not accepted"})
    return await call_next(request)


def _init_otel(app):
    # B49 thread (b) — app-level spans → Tempo OTLP. OPT-IN via OTEL_EXPORTER_OTLP_ENDPOINT (set in the k8s env to
    # http://tempo.monitoring.svc.cluster.local:4318); unset → no-op, so local/dev runs and tests need no collector.
    # HTTP OTLP (:4318), NOT gRPC (:4317) — the meshed→unmeshed hop hits the same http2-framing snag the Grafana→Tempo
    # gRPC path shows, so a plain HTTP POST sidesteps it. FastAPI instrumentation extracts the incoming Istio
    # traceparent, so these spans nest UNDER the mesh span (full request → handler → outbound httpx picture).
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    provider = TracerProvider(resource=Resource.create(
        {"service.name": os.environ.get("OTEL_SERVICE_NAME", "weyland-tool-server")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # reads OTEL_EXPORTER_OTLP_ENDPOINT (+ /v1/traces)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()


_init_otel(app)


class ContextSearchRequest(BaseModel):
    query: str
    limit: int = 5


class PipelineTriggerRequest(BaseModel):
    # Constrained to the real Dagster jobs so an agent can't pass a non-existent name (Dagster rejects
    # those → "Dagster launch failed"). fastapi-mcp surfaces this as an enum in the MCP tool schema, so the
    # caller sees the valid values instead of guessing.
    job_name: Literal[
        "weyland_ingestion_job", "weyland_eval_job", "weyland_eval_score_job"
    ] = "weyland_ingestion_job"


class AskRequest(BaseModel):
    query: str
    backend: str = "pgvector"
    limit: int = 5
    # None -> fall back to OLLAMA_MODEL. Pass any model pulled on the Ollama host
    # (see GET /models) to override per request.
    model: str | None = None
    # Optional Langfuse session grouping — pass a stable id (e.g. an open-webui conversation id)
    # to collapse a multi-turn exchange into one session; unset → this ask is its own session.
    session_id: str | None = None
    # False = do not trace this ask to Langfuse. For bulk/offline callers (the weyland_eval_job matrix): each
    # `rag-generate` observation fires up to 9 online LLM-as-judge rules on rogueone's gpt-oss:20b, which evicted the
    # model under test twice per eval question (2026-09-29). MLflow tracing is unaffected.
    langfuse: bool = True


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
        # FP: internal health-check — URL is built from trusted in-cluster env constants, never user input (not SSRF).
        with urllib.request.urlopen(url, timeout=5) as resp:  # nosemgrep
            data = json.loads(resp.read().decode())
        return {"status": "ok", "collections": data.get("result", {}).get("collections", [])}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _check_weaviate() -> dict:
    try:
        url = f"http://{WEAVIATE_HOST}:{WEAVIATE_PORT}/v1/.well-known/ready"
        # FP: internal health-check — URL is built from trusted in-cluster env constants, never user input (not SSRF).
        with urllib.request.urlopen(url, timeout=5) as resp:  # nosemgrep
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
        resp = httpx.get(f"{OLLAMA_BASE_URL}/models", timeout=5, headers=_ollama_headers())
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
        headers=_ollama_headers(),
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


@app.get("/status", tags=["mcp"], operation_id="status")
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


@app.post("/context/search", tags=["mcp"], operation_id="context_search")
def context_search(request: ContextSearchRequest, backend: str = Query(default="pgvector"),
                   actor: str | None = Depends(_actor)):
    if backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{backend}'. Valid options: {sorted(VALID_BACKENDS)}",
        )
    request_id = str(uuid.uuid4())
    blocked = _guard(Hook.INPUT, request_id, {"query": request.query}, actor)
    if blocked is not None:
        raise HTTPException(status_code=403, detail=f"blocked by {blocked.validator}: {blocked.reason}")
    results = SEARCH_FNS[backend](request.query, request.limit)
    return {"query": request.query, "results": results}


@app.get("/models", tags=["mcp"], operation_id="list_models")
def list_models():
    """Models available on the Ollama endpoint, for client-side selection in /context/ask."""
    check = _check_ollama()
    if check["status"] != "ok":
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {check.get('detail')}")
    return {"default": OLLAMA_MODEL, "available": check["models"]}


@app.post("/context/ask", tags=["mcp"], operation_id="context_ask")
def context_ask(request: AskRequest, actor: str | None = Depends(_actor)):
    """RAG: retrieve top-k chunks from a backend, then have the local model synthesize a
    grounded answer. `model` is selectable per request (defaults to OLLAMA_MODEL)."""
    if request.backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{request.backend}'. Valid options: {sorted(VALID_BACKENDS)}",
        )
    request_id = str(uuid.uuid4())
    blocked = _guard(Hook.INPUT, request_id, {"query": request.query}, actor)
    if blocked is not None:
        raise HTTPException(status_code=403, detail=f"blocked by {blocked.validator}: {blocked.reason}")
    model = request.model or OLLAMA_MODEL
    with _span("context_ask", span_type="CHAIN") as parent:
        if parent is not None:
            parent.set_inputs({"query": request.query, "backend": request.backend, "model": model, "limit": request.limit})
        with _span("retrieve", span_type="RETRIEVER") as rspan:
            chunks = SEARCH_FNS[request.backend](request.query, request.limit)
            if rspan is not None:
                rspan.set_outputs({"num_chunks": len(chunks)})
        system_prompt = load_prompt("rag_system", RAG_SYSTEM_PROMPT)   # B100 P2 — live from the Prompt Registry (fail-safe)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{_build_context(chunks)}\n\nQuestion: {request.query}"},
        ]
        with _span("generate", span_type="LLM") as gspan, \
             _lf_generation("rag-generate", model, messages, "rag_system",
                            request.session_id or request_id, actor, enabled=request.langfuse) as lgen:   # B103 — Langfuse link + session, dual with MLflow
            if gspan is not None:
                gspan.set_inputs({"model": model, "context_chunks": len(chunks), "prompt_version": loaded_version("rag_system")})
            try:
                answer = _ollama_chat(messages, model)
            except httpx.HTTPError as e:
                raise HTTPException(status_code=502, detail=f"LLM call failed ({model}): {e}")
            if gspan is not None:
                gspan.set_outputs({"answer": answer})
            if lgen is not None:
                lgen.update(output=answer)
        if parent is not None:
            parent.set_outputs({"answer": answer, "num_sources": len(chunks)})
    # OUTPUT hook: grounding (answer vs retrieved chunks) + PII/toxicity on the answer.
    out_blocked = _guard(Hook.OUTPUT, request_id, {"query": request.query, "answer": answer, "sources": chunks}, actor)
    if out_blocked is not None:
        raise HTTPException(status_code=403, detail=f"blocked by {out_blocked.validator}: {out_blocked.reason}")
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


@app.post("/pipeline/trigger", tags=["mcp-act"], operation_id="pipeline_trigger",
           responses={403: {"description": "The act guard refused this act (policy.gate), or the guard was unavailable"}})
def pipeline_trigger(request: PipelineTriggerRequest, actor: str | None = Depends(_actor)):
    """Trigger a Dagster job. Default (and usual choice) is `weyland_ingestion_job` — the docs/code
    ingestion pipeline. `job_name` must be one of the three defined jobs; leave it at the default to
    re-ingest the knowledge base."""
    request_id = str(uuid.uuid4())
    _guard_act(request_id, "pipeline/trigger", actor, {"job_name": request.job_name})
    return _launch_dagster_job(request.job_name)


# --- B4 eval endpoints (single-path eval + leaderboard; see docs/b4-eval-runbook.md) ---
def _eval_pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD, connect_timeout=5
    )


@app.post("/evals/run", tags=["mcp-act"], operation_id="evals_run",
           responses={403: {"description": "The act guard refused this act (policy.gate), or the guard was unavailable"}})
def evals_run(actor: str | None = Depends(_actor)):
    """Run the eval matrix (generate a question set + run all models). LONG-RUNNING — ~40-60 min of CPU
    and competes with the single loaded Ollama model; fire deliberately, not casually. Then POST /evals/score."""
    request_id = str(uuid.uuid4())
    _guard_act(request_id, "evals/run", actor)
    return _launch_dagster_job("weyland_eval_job")


@app.post("/evals/score", tags=["mcp-act"], operation_id="evals_score",
           responses={403: {"description": "The act guard refused this act (policy.gate), or the guard was unavailable"}})
def evals_score(actor: str | None = Depends(_actor)):
    """Judge-panel scoring of the latest completed matrix run. LONG-RUNNING — ~70 min of CPU. Run after
    /evals/run has completed."""
    request_id = str(uuid.uuid4())
    _guard_act(request_id, "evals/score", actor)
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


# --- Prometheus scrape target -----------------------------------------------------
# A plain route (not a sub-app mount) so it serves at exactly /metrics with no trailing-slash
# redirect — clean for Prometheus (B5) scraping. Untagged, so it stays out of the MCP surface.
# NOTE (B70 Part 2): guardrail verdict/latency metrics moved to weyland-guard's /metrics; this now serves only the
# default process/GC collectors (its ServiceMonitor was retired — pod cpu/mem come from cAdvisor anyway).
@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- MCP servers (B111 Option C: FastMCP, replacing fastapi-mcp 0.4.0) ------------
# Constructed last so every route above is already registered for introspection.
#
# fastapi-mcp 0.4.0's streamable-HTTP mount hangs under starlette 1.x (request.body() never
# resolves → ClientDisconnect). FastMCP 3.x (mcp SDK 1.28-native) replaces it. from_fastapi
# introspects the tagged routes into MCP tools and, on each call, replays them in-process against
# THIS app (httpx ASGITransport), forwarding the inbound MCP request headers via get_http_headers()
# — so x-forwarded-consumer still reaches the `_actor` dependency (the B17+B19 actor lane).
# route_maps keep each surface to its own tag; every other route is EXCLUDEd. (Validated end-to-end
# 2026-07-31: no hang, tag isolation, and actor forwarding all confirmed under starlette 1.3.1.)
#
# READ surface (B2): tools tagged "mcp" (/status, /context/search, /context/ask, /models) at /mcp.
#   Consumer: the weyland-mcp-compositor "context" upstream + direct clients — http://<host>:30080/mcp
# ACT surface (B14): tools tagged "mcp-act" (/pipeline/trigger, /evals/run, /evals/score) at /mcp-act,
# fronted by the gateway (B17+B19) with auth/policy while /mcp stays open. Read never implies act;
# every act call passes the `act` hook: policy.audit records it and policy.gate decides it, ENFORCED by _guard_act
# (403 before anything launches; B207) → guardrail_verdicts.
mcp_read = FastMCP.from_fastapi(app, name="weyland-system-view",
    route_maps=[RouteMap(tags={"mcp"}, mcp_type=MCPType.TOOL), RouteMap(mcp_type=MCPType.EXCLUDE)])
mcp_act = FastMCP.from_fastapi(app, name="weyland-act",
    route_maps=[RouteMap(tags={"mcp-act"}, mcp_type=MCPType.TOOL), RouteMap(mcp_type=MCPType.EXCLUDE)])
# http_app(path="/") serves MCP at the sub-app root; mounted so external paths stay /mcp and /mcp-act
# (both /mcp and /mcp/ handshake — validated). stateless_http=True (no session affinity needed for
# these tools) + json_response=True (plain JSON). The two .lifespan()s are run by the app lifespan above.
_mcp_read_app = mcp_read.http_app(path="/", stateless_http=True, json_response=True)
_mcp_act_app = mcp_act.http_app(path="/", stateless_http=True, json_response=True)
app.mount("/mcp-act", _mcp_act_app)
app.mount("/mcp", _mcp_read_app)
