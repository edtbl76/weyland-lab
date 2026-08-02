"""realm-of-agents — the A2A front door for the Realm of Agents (B17).

One multiplexed pod, realm-partitioned inside. Exposes A2A-shaped Agent Cards (discover the whole realm at one URL, or
any agent at its own) and a task endpoint per agent. `/route` runs Gná (dispatch → best agent). Leads delegate to their
members over LangGraph; cross-realm calls go over these HTTP/A2A endpoints.

Slice 1 (first wave): Gná dispatch · Kvasir · Verðandi (grafana tools) · Odin delegating to Mímir + Brokkr. Every other
agent is declared in the roster and runs generically (role prompt + lane + tool slice); leads gain delegation as their
members come online."""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

import mlflow

import a2a
import cards
import router as gna
from config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI, VERSION
from roster import BY_KEY, ROSTER, REALMS, in_realm

_REQS = Counter("realm_requests_total", "Agent task requests", ["agent", "outcome"])
_LATENCY = Histogram("realm_request_seconds", "Per-task latency (s)", ["agent"])
_ready = {"ok": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Every agent run (and its full deliverable) is captured as an MLflow trace. Fail-safe: MLflow unreachable never
    # blocks startup or a request — same ethos as the operator's tracing.
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
        mlflow.langchain.autolog()
        print("[realm] MLflow autolog enabled", flush=True)
    except Exception as exc:
        print(f"[realm] MLflow autolog disabled: {exc}", flush=True)
    _ready["ok"] = True
    yield


app = FastAPI(title="Weyland — Realm of Agents", version=VERSION, lifespan=lifespan)
app.include_router(a2a.router)   # A2A JSON-RPC binding: POST /a2a (Gná) and /a2a/{key} (specific agent)


class TaskRequest(BaseModel):
    message: str
    history: list | None = None


# --- Discovery (A2A Agent Cards) ---------------------------------------------------------------------------------
@app.get("/.well-known/agent-card.json")
def root_card(request: Request):
    return cards.root_card(str(request.base_url))


@app.get("/agents")
def list_agents(request: Request):
    """The whole roster as cards, plus a realm index for humans/UIs."""
    return {"realms": {r: [a.key for a in in_realm(r)] for r in REALMS}, "agents": cards.all_cards(str(request.base_url))}


@app.get("/agents/{key}/.well-known/agent-card.json")
@app.get("/agents/{key}/card")
def agent_card(key: str, request: Request):
    spec = BY_KEY.get(key)
    if not spec:
        raise HTTPException(404, f"no agent '{key}'")
    return cards.card(spec, str(request.base_url))


# --- Tasking -----------------------------------------------------------------------------------------------------
@app.post("/agents/{key}/message")
async def send_message(key: str, req: TaskRequest):
    """Send a task to a specific agent (a lead delegates; a plain agent answers directly)."""
    spec = BY_KEY.get(key)
    if not spec:
        raise HTTPException(404, f"no agent '{key}'")
    t0 = time.monotonic()
    try:
        answer = await gna.run_agent(spec, req.message, req.history)
    except Exception as exc:
        _REQS.labels(key, "error").inc()
        raise HTTPException(502, f"{spec.god} run failed: {exc}")
    _LATENCY.labels(key).observe(time.monotonic() - t0)
    _REQS.labels(key, "ok").inc()
    return {"agent": key, "god": spec.god, "role": spec.role, "realm": spec.realm, "answer": answer}


@app.post("/route")
async def route(req: TaskRequest):
    """Gná: classify the task, run the best-fit agent, and report which one handled it."""
    t0 = time.monotonic()
    try:
        key, answer = await gna.dispatch(req.message, req.history)
    except Exception as exc:
        _REQS.labels("gna", "error").inc()
        raise HTTPException(502, f"dispatch failed: {exc}")
    _LATENCY.labels("gna").observe(time.monotonic() - t0)
    _REQS.labels(key, "ok").inc()
    return {"routed_to": key, "god": BY_KEY[key].god, "role": BY_KEY[key].role, "realm": BY_KEY[key].realm, "answer": answer}


# --- Ops ---------------------------------------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "realm-of-agents", "version": VERSION, "agents": len(ROSTER)}


@app.get("/ready")
def ready():
    if _ready["ok"]:
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "loading"})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
