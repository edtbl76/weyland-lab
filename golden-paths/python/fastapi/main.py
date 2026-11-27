"""Golden path — Python / FastAPI (B153; deep contract v2 since B260).

A blessed, paved-road FastAPI service template. It is RUNNABLE, EPHEMERAL (built + spun up as a run-to-completion
Job to exercise itself, then torn down — never a Deployment), and EXTENDABLE (scaffold a real service FROM it).

The minimal contract (docs/design/golden-paths.md): GET /health, /ready, /metrics, /hello.
Deep contract v2 (docs/concepts/golden-path-capabilities.md), each row in FastAPI's own idiom:
  C1 routing        GET /items?limit&offset, GET /items/{item_id}, POST /items
  C2 validation     Pydantic models + Query constraints; a bad request is 422 with per-field errors
  C3 errors         one envelope {"error": {"code", "message", "request_id"}} from exception handlers
  C4 middleware     X-Request-ID (echoed or generated) + one JSON access-log line per request
  C5 metrics        http_requests_total{route,status} + http_request_duration_seconds, per route template
  C6 config         Settings.from_env(): GOLDEN_GREETING validated at startup (empty = refuse to start)
  C7 DI             an ItemStore injected with Depends; in-memory by default, the real ones by env (items_backends)
  C8 lifecycle      the lifespan opens the store and flips /ready; shutdown closes it (uvicorn drains on SIGTERM)
  C9 tests          TestClient, one test per row (test_main.py)
  C10 OpenAPI       /openapi.json, native
  C11 tracing       setup_tracing(): OTel spans per request when OTEL_EXPORTER_OTLP_ENDPOINT is set; no-op otherwise

FastAPI is the estate's blessed Python service framework, and it is OpenAPI-native, so the B155 API lifecycle
captures its contract from /openapi.json for free.

TO SCAFFOLD A REAL SERVICE: `scripts/new-service.sh python/fastapi <your-service>`.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from items_store import InMemoryItemStore, ItemStore  # the shared store (a synced copy, B261); re-exported for tests

# The one place a scaffolded service is renamed (scripts/new-service.sh rewrites this token).
SERVICE_NAME = "golden-python-fastapi"
DEFAULT_GREETING = "hello, weyland"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(SERVICE_NAME)
access_log = logging.getLogger(f"{SERVICE_NAME}.access")

_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")
_requests = Counter("http_requests_total", "HTTP requests by route template and status", ["route", "status"])
_latency = Histogram("http_request_duration_seconds", "HTTP request latency by route template", ["route"])


# --- C6 config -------------------------------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Settings:
    greeting: str = DEFAULT_GREETING

    def __post_init__(self) -> None:
        if not self.greeting.strip():
            raise ValueError("GOLDEN_GREETING must not be empty")

    @classmethod
    def from_env(cls) -> Settings:
        """Read and validate config once, at startup: a bad value stops the service before it serves."""
        return cls(greeting=os.environ.get("GOLDEN_GREETING", DEFAULT_GREETING))


# --- C2 the typed models ---------------------------------------------------------------------------------------
class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=5)


class Item(ItemIn):
    id: int


# --- C7 the store (shared, framework-neutral: items_store.py is a synced copy, B261) -------------------------


def store_from_env() -> ItemStore:
    """GOLDEN_DATABASE_URL (and the optional cache/event settings) select the real backends; the in-memory store
    otherwise. The backends module is imported only when configured, and nothing connects until the lifespan opens it."""
    if not os.environ.get("GOLDEN_DATABASE_URL"):
        return InMemoryItemStore()
    import items_backends
    return items_backends.build_store_from_env()


# --- C3 errors -----------------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or request.headers.get("x-request-id", "")


def _envelope(request: Request, status: int, code: str, message: str, fields: list | None = None) -> JSONResponse:
    rid = _request_id(request)
    error = {"code": code, "message": message, "request_id": rid}
    if fields is not None:
        error["fields"] = fields
    return JSONResponse({"error": error}, status_code=status, headers={"X-Request-ID": rid})


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return _envelope(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = [{"field": str(e["loc"][-1]), "message": e["msg"]} for e in exc.errors()]
        return _envelope(request, 422, "validation_failed", "the request is invalid", fields)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _envelope(request, exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")          # the detail goes to the log, never to the client
        return _envelope(request, 500, "internal", "internal error")


# --- C4 + C5 middleware -----------------------------------------------------------------------------------------
def _install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", "unmatched")
            _requests.labels(route=route, status=str(status)).inc()
            _latency.labels(route=route).observe(elapsed)
            access_log.info(json.dumps({"method": request.method, "path": request.url.path, "status": status,
                                        "request_id": rid, "duration_ms": round(elapsed * 1000, 3)}))


# --- the app -------------------------------------------------------------------------------------------------
def get_store(request: Request) -> ItemStore:
    return request.app.state.store


def create_app(settings: Settings | None = None, store: ItemStore | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or store_from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store.open()
        app.state.ready = True
        log.info(json.dumps({"event": "started", "service": SERVICE_NAME}))
        yield
        app.state.ready = False
        app.state.store.close()

    app = FastAPI(title=SERVICE_NAME, version="2.0.0", lifespan=lifespan)
    app.state.settings, app.state.store, app.state.ready = settings, store, False
    _install_error_handlers(app)
    _install_middleware(app)

    @app.get("/health")
    def health() -> dict:
        """Liveness — the process is up."""
        return {"status": "ok"}

    @app.get("/ready")
    def ready(request: Request) -> dict:
        """Readiness — 503 until the lifespan has opened the store (the SMOKE-gate + Job probe)."""
        if not request.app.state.ready:
            raise ApiError(503, "not_ready", "the service is starting")
        return {"status": "ready"}

    @app.get("/metrics")
    def metrics() -> PlainTextResponse:
        """Prometheus exposition (a ServiceMonitor scrapes this in a scaffolded service)."""
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/hello")
    def hello(request: Request) -> dict:
        """The demo endpoint — the known payload the ephemeral Job asserts; the greeting is config (C6)."""
        _hello_hits.inc()
        return {"service": SERVICE_NAME, "message": request.app.state.settings.greeting}

    @app.get("/items")
    def list_items(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   items: ItemStore = Depends(get_store)) -> dict:
        return {"items": items.list(limit, offset), "limit": limit, "offset": offset}

    @app.get("/items/{item_id}")
    def get_item(item_id: int, items: ItemStore = Depends(get_store)) -> Item:
        found = items.get(item_id)
        if found is None:
            raise ApiError(404, "not_found", f"item {item_id} not found")
        return Item(**found)

    @app.post("/items", status_code=201)
    def create_item(item: ItemIn, items: ItemStore = Depends(get_store)) -> Item:
        return Item(**items.create(item.name, item.tags))

    return app


# --- C11 tracing ------------------------------------------------------------------------------------------------
def setup_tracing(app: FastAPI, exporter=None):
    """OTel spans per request when OTEL_EXPORTER_OTLP_ENDPOINT is set (or an exporter is given); else a no-op.
    Returns the tracer provider, or None when tracing is off."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if exporter is None and not endpoint:
        return None
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    return provider


app = create_app()
setup_tracing(app)
