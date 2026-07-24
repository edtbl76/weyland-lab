"""weyland-operator — the lab operator agent (B66 Part 1: read-only HTTP surface).

A LangGraph ReAct agent (gpt-oss:20b) over the tool-server's read tools. Part 1 exposes it as `POST /operator/ask`
for testing + k8s probes/scrape; Parts 2–3 add Telegram ingress, Postgres session memory, and the act confirm-step.
Guards the inbound message + outbound reply via weyland-guard (fail-open). Each /ask is one MLflow Trace."""
import os
import time
import uuid
from contextlib import asynccontextmanager

import mlflow
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

import agent
from guard import guard

VERSION = "0.1.0"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "operator")

_REQS = Counter("operator_requests_total", "Operator /ask requests", ["outcome"])
_LATENCY = Histogram("operator_request_seconds", "End-to-end /operator/ask latency (s)")
_ready = {"ok": False}


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
    _ready["ok"] = True
    yield


app = FastAPI(title="Weyland Operator", lifespan=lifespan)


def _actor(x_forwarded_consumer: str | None = Header(default=None)) -> str | None:
    return x_forwarded_consumer


class AskRequest(BaseModel):
    message: str


@app.post("/operator/ask")
def operator_ask(req: AskRequest, actor: str | None = Depends(_actor)):
    request_id = str(uuid.uuid4())
    if guard("input", request_id, {"query": req.message}, actor):
        _REQS.labels("blocked").inc()
        raise HTTPException(403, "blocked by input guard")
    t0 = time.monotonic()
    try:
        reply = agent.run(req.message)
    except Exception as exc:
        _REQS.labels("error").inc()
        raise HTTPException(502, f"operator run failed: {exc}")
    _LATENCY.observe(time.monotonic() - t0)
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
