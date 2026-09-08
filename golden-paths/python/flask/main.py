"""Golden path — Python / Flask (B153).

Blessed paved-road Flask (WSGI) service. Runnable · ephemeral · extendable. Conforms to the
golden-path contract (docs/design/golden-paths.md): GET /health · /ready · /metrics · /hello.
Flask = the ubiquitous minimal WSGI framework; served by gunicorn in the image.

Scaffold a real service FROM it: scripts/new-service.sh python/flask <your-service>.
"""
import logging

from flask import Flask, jsonify
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

SERVICE_NAME = "golden-python-flask"

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"' + SERVICE_NAME + '","msg":"%(message)s"}')
log = logging.getLogger(SERVICE_NAME)

app = Flask(SERVICE_NAME)
_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")


@app.get("/health")
def health():
    """Liveness."""
    return jsonify(status="ok")


@app.get("/ready")
def ready():
    """Readiness — the SMOKE-gate + Job probe."""
    return jsonify(status="ready")


@app.get("/metrics")
def metrics():
    """Prometheus exposition."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.get("/hello")
def hello():
    """The demo endpoint — the known payload the ephemeral Job asserts."""
    _hello_hits.inc()
    log.info("served /hello")
    return jsonify(service=SERVICE_NAME, message="hello, weyland")
