"""Golden path — Python / FastAPI (B153).

A blessed, paved-road FastAPI service template. It is RUNNABLE, EPHEMERAL (built + spun up as a
run-to-completion Job to exercise itself, then torn down — never a Deployment), and EXTENDABLE (scaffold
a real service FROM it). It conforms to the framework-agnostic golden-path CONTRACT
(docs/design/golden-paths.md):

    GET /health   liveness  -> {"status": "ok"}
    GET /ready    readiness -> {"status": "ready"}    (the SMOKE-gate probe)
    GET /metrics  Prometheus exposition
    GET /hello    the demo endpoint -> a known JSON payload the ephemeral Job asserts

FastAPI is the estate's blessed Python service framework — every HTTP service in the lab (tool-server,
weyland-guard, weyland-agent, weyland-operator, realm-of-agents) is FastAPI, and it is OpenAPI-native, so
the B155 API lifecycle captures its contract from /openapi.json for free.

TO SCAFFOLD A REAL SERVICE: `scripts/new-service.sh python/fastapi <your-service>` (renames SERVICE_NAME,
fills the onboarding declaration in README.md, and drops you a runnable, gate-passing starting point).
"""
import logging

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

# The one place a scaffolded service is renamed (scripts/new-service.sh rewrites this token).
SERVICE_NAME = "golden-python-fastapi"

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"' + SERVICE_NAME + '","msg":"%(message)s"}')
log = logging.getLogger(SERVICE_NAME)

app = FastAPI(title=SERVICE_NAME, version="1.0.0")

_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")


@app.get("/health")
def health() -> dict:
    """Liveness — the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness — the service can serve (dependencies are up). The SMOKE-gate + Job probe."""
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    """Prometheus exposition (a ServiceMonitor scrapes this in a scaffolded service)."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/hello")
def hello() -> dict:
    """The demo endpoint — returns the known payload the ephemeral Job asserts."""
    _hello_hits.inc()
    log.info("served /hello")
    return {"service": SERVICE_NAME, "message": "hello, weyland"}
