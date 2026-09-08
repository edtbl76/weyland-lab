"""Golden path — Python / Litestar (B153).

Blessed paved-road Litestar (modern async, batteries-included) service. Runnable · ephemeral ·
extendable. Conforms to the golden-path contract (docs/design/golden-paths.md): GET /health · /ready ·
/metrics · /hello. ASGI, served by uvicorn in the image.

Scaffold a real service FROM it: scripts/new-service.sh python/litestar <your-service>.
"""
import logging

from litestar import Litestar, Response, get
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

SERVICE_NAME = "golden-python-litestar"

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"' + SERVICE_NAME + '","msg":"%(message)s"}')
log = logging.getLogger(SERVICE_NAME)

_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")


@get("/health", sync_to_thread=False)
def health() -> dict:
    """Liveness."""
    return {"status": "ok"}


@get("/ready", sync_to_thread=False)
def ready() -> dict:
    """Readiness — the SMOKE-gate + Job probe."""
    return {"status": "ready"}


@get("/metrics", sync_to_thread=False)
def metrics() -> Response:
    """Prometheus exposition."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@get("/hello", sync_to_thread=False)
def hello() -> dict:
    """The demo endpoint — the known payload the ephemeral Job asserts."""
    _hello_hits.inc()
    log.info("served /hello")
    return {"service": SERVICE_NAME, "message": "hello, weyland"}


app = Litestar(route_handlers=[health, ready, metrics, hello])
