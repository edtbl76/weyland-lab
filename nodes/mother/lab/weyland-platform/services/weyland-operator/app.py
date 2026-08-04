"""weyland-operator — the lab operator agent (B66 Part 1: read-only HTTP surface).

A LangGraph ReAct agent (gpt-oss:20b) over the tool-server's read tools. Part 1 exposes it as `POST /operator/ask`
for testing + k8s probes/scrape; Parts 2–3 add Telegram ingress, Postgres session memory, and the act confirm-step.
Guards the inbound message + outbound reply via weyland-guard (fail-open). Each /ask is one MLflow Trace."""
import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager

import mlflow
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

import act
import agent
import incidents
import ingress
import session
import telegram
from guard import guard

VERSION = "0.2.0"   # B45 — enrich-only incident sweep
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "operator")

_REQS = Counter("operator_requests_total", "Operator /ask requests", ["outcome"])
_LATENCY = Histogram("operator_request_seconds", "End-to-end /operator/ask latency (s)")
_ready = {"ok": False}
_ingress_task = None
_sweep_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT)
    except Exception as exc:
        print(f"[mlflow] set_experiment failed: {exc}", flush=True)
    try:
        mlflow.langchain.autolog()          # LangGraph + LLM + tool spans (advisory — never blocks startup)
    except Exception as exc:
        print(f"[mlflow] langchain autolog disabled: {exc}", flush=True)
    # Telegram ingress + Postgres sessions (Part 2). Both gated on a bot token so the HTTP /operator/ask surface
    # still runs standalone (no DB/token) for testing + probes.
    global _ingress_task, _sweep_task
    if telegram.configured():
        try:
            session.init()
            session.init_incidents()          # B45 — the incident-sweep dedup table
        except Exception as exc:
            print(f"[session] init failed (per-message ops will retry): {exc}", flush=True)
        _ingress_task = asyncio.create_task(ingress.poll_loop())
        print("[telegram] long-poll ingress started", flush=True)
        if incidents.enabled():               # B45 — enrich-only incident sweep, OFF the critical alert path
            _sweep_task = asyncio.create_task(incidents.sweep_loop())
            print("[incidents] B45 incident sweep started", flush=True)
    else:
        print("[telegram] no TELEGRAM_BOT_TOKEN — ingress disabled (HTTP /operator/ask only)", flush=True)
    _ready["ok"] = True
    yield
    for _t in (_ingress_task, _sweep_task):
        if _t:
            _t.cancel()


app = FastAPI(title="Weyland Operator", lifespan=lifespan)


def _actor(x_forwarded_consumer: str | None = Header(default=None)) -> str | None:
    return x_forwarded_consumer


class AskRequest(BaseModel):
    message: str


@app.post("/operator/ask")
async def operator_ask(req: AskRequest, actor: str | None = Depends(_actor)):
    request_id = str(uuid.uuid4())
    if guard("input", request_id, {"query": req.message}, actor):
        _REQS.labels("blocked").inc()
        raise HTTPException(403, "blocked by input guard")
    t0 = time.monotonic()
    try:
        reply, proposal = await agent.run(req.message)
    except Exception as exc:
        _REQS.labels("error").inc()
        raise HTTPException(502, f"operator run failed: {exc}")
    _LATENCY.observe(time.monotonic() - t0)
    # /operator/ask is stateless — surface a proposed action but NEVER fire (acts need the Telegram confirm flow).
    if proposal and proposal.get("tool"):
        reply = f"[proposed action — acts require the Telegram confirm flow] {act.describe(proposal)}"
    # sources=[] → the grounding validator is N/A (the operator grounds on tool results, not RAG chunks); the
    # output guard still screens the reply for toxicity.
    if guard("output", request_id, {"answer": reply, "sources": []}, actor):
        _REQS.labels("blocked").inc()
        raise HTTPException(403, "blocked by output guard")
    _REQS.labels("ok").inc()
    return {"message": req.message, "reply": reply}


@app.get("/health")
def health():
    return {"status": "ok", "service": "weyland-operator", "version": VERSION}


@app.get("/ready")
def ready():
    if _ready["ok"]:
        return {"status": "ready"}
    return JSONResponse(status_code=503, content={"status": "loading"})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
