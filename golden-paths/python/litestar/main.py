"""Golden path — Python / Litestar (B153; deep contract v2 since B261).

Blessed paved-road Litestar service. Runnable · ephemeral · extendable. ASGI, served by uvicorn (`main:serve`,
a factory). Scaffold FROM it: scripts/new-service.sh python/litestar <your-service>.

The minimal contract (docs/design/golden-paths.md): GET /health, /ready, /metrics, /hello.
Deep contract v2 (docs/concepts/golden-path-capabilities.md), in Litestar's own idiom:
  C1 routing        GET /items?limit&offset, GET /items/{item_id:int}, POST /items
  C2 validation     msgspec Structs + Parameter constraints (native); invalid = 422 with per-field errors
  C3 errors         one envelope {"error": {"code", "message", "request_id"}} from exception handlers
  C4 middleware     an ASGI middleware: X-Request-ID (echoed or generated) + one JSON access-log line
  C5 metrics        http_requests_total{route,status} + http_request_duration_seconds (route = the path template)
  C6 config         Settings.from_env(): GOLDEN_GREETING validated at startup (empty refuses to start)
  C7 DI             the shared ItemStore through Provide (Litestar's dependency injection)
  C8 lifecycle      on_startup opens the store and flips /ready (503 before); on_shutdown closes it
  C9 tests          litestar.testing.TestClient, test_main.py
  C10 OpenAPI       /schema/openapi.json, native
  C11 tracing       setup_tracing() + Litestar's OpenTelemetry plugin, when OTEL_EXPORTER_OTLP_ENDPOINT is set
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import time
import uuid
from typing import Annotated, Any

import msgspec
from litestar import Litestar, Request, Response, get, post
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide
from litestar.exceptions import HTTPException, ValidationException
from litestar.params import FromPath, JSONBody, Parameter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from items_store import InMemoryItemStore, ItemStore  # the shared store (a synced copy, B261)

SERVICE_NAME = "golden-python-litestar"
DEFAULT_GREETING = "hello, weyland"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(SERVICE_NAME)
access_log = logging.getLogger(f"{SERVICE_NAME}.access")

_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")
_requests = Counter("http_requests_total", "HTTP requests by route template and status", ["route", "status"])
_latency = Histogram("http_request_duration_seconds", "HTTP request latency by route template", ["route"])


# --- C6 config -----------------------------------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Settings:
    greeting: str = DEFAULT_GREETING

    def __post_init__(self) -> None:
        if not self.greeting.strip():
            raise ValueError("GOLDEN_GREETING must not be empty")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(greeting=os.environ.get("GOLDEN_GREETING", DEFAULT_GREETING))


def store_from_env() -> ItemStore:
    """GOLDEN_DATABASE_URL selects the shared real backends; the in-memory store otherwise (nothing connects here)."""
    if not os.environ.get("GOLDEN_DATABASE_URL"):
        return InMemoryItemStore()
    import items_backends
    return items_backends.build_store_from_env()


# --- C2 the typed body ----------------------------------------------------------------------------------------------
class ItemIn(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=64)]
    tags: Annotated[list[str], msgspec.Meta(max_length=5)] = []


# --- C3 errors -----------------------------------------------------------------------------------------------------
class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(status_code=status, detail=message)
        self.code = code


_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}
_INDEX = re.compile(r"\[(\d+)\]")


def _envelope(request: Request, status: int, code: str, message: str, fields: list | None = None) -> Response:
    rid = request.scope.get("golden_request_id", "")
    error = {"code": code, "message": message, "request_id": rid}
    if fields is not None:
        error["fields"] = fields
    return Response({"error": error}, status_code=status, headers={"X-Request-ID": rid})


def _field(key: str) -> str:
    """msgspec/Litestar keys ("tags[1]", "$.tags[1]") as the contract's "tags.1"."""
    return _INDEX.sub(r".\1", key.removeprefix("$.")).lstrip(".")


def _on_api_error(request: Request, exc: ApiError) -> Response:
    return _envelope(request, exc.status_code, exc.code, exc.detail)


_MISSING = re.compile(r"missing required field `([^`]+)`")


def _on_validation(request: Request, exc: ValidationException) -> Response:
    fields = []
    for e in exc.extra if isinstance(exc.extra, list) else []:
        message, key = str(e.get("message", "")), str(e.get("key", ""))
        missing = _MISSING.search(message)          # msgspec names a missing field in the message, keyed "data"
        fields.append({"field": missing.group(1) if missing else _field(key), "message": message})
    return _envelope(request, 422, "validation_failed", "the request is invalid", fields)


def _on_http(request: Request, exc: HTTPException) -> Response:
    return _envelope(request, exc.status_code, _HTTP_CODES.get(exc.status_code, "http_error"), exc.detail)


def _on_unhandled(request: Request, exc: Exception) -> Response:
    log.exception("unhandled error")              # the detail goes to the log, never to the client
    return _envelope(request, 500, "internal", "internal error")


# --- C4 + C5 middleware --------------------------------------------------------------------------------------------
class RequestContextMiddleware:
    """ASGI middleware: request id in and out, one access-log line, per-route metrics."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        rid = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex
        scope["golden_request_id"] = rid
        started, seen = time.perf_counter(), {"status": 500}

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                seen["status"] = message["status"]
                message["headers"] = [h for h in message.get("headers", []) if h[0].lower() != b"x-request-id"]
                message["headers"].append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            elapsed = time.perf_counter() - started
            route = scope.get("path_template") or "unmatched"
            _requests.labels(route=route, status=str(seen["status"])).inc()
            _latency.labels(route=route).observe(elapsed)
            access_log.info(json.dumps({"method": scope["method"], "path": scope["path"], "status": seen["status"],
                                        "request_id": rid, "duration_ms": round(elapsed * 1000, 3)}))


# An injected object is not request data: marked as a named dependency (Litestar 2.23+), it is injected by name and
# not validated as input (msgspec cannot validate a Protocol; untyped, it was a 500 on every request).
Store = NamedDependency[Any]   # the ItemStore (the Protocol is the contract; Any is what msgspec can pass through)


# --- C1 routes -----------------------------------------------------------------------------------------------------
@get("/health", sync_to_thread=False)
def health() -> dict:
    """Liveness."""
    return {"status": "ok"}


@get("/ready", sync_to_thread=False)
def ready(state: State) -> dict:
    """Readiness — 503 until on_startup has opened the store (the SMOKE-gate + Job probe)."""
    if not state.get("ready"):
        raise ApiError(503, "not_ready", "the service is starting")
    return {"status": "ready"}


@get("/metrics", sync_to_thread=False)
def metrics() -> Response:
    """Prometheus exposition."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@get("/hello", sync_to_thread=False)
def hello(state: State) -> dict:
    """The demo endpoint — the greeting is config (C6)."""
    _hello_hits.inc()
    return {"service": SERVICE_NAME, "message": state.settings.greeting}


@get("/items", sync_to_thread=False)
def list_items(store: Store, limit: Annotated[int, Parameter(ge=1, le=100)] = 20,
               offset: Annotated[int, Parameter(ge=0)] = 0) -> dict:
    return {"items": store.list(limit, offset), "limit": limit, "offset": offset}


@get("/items/{item_id:int}", sync_to_thread=False)
def get_item(store: Store, item_id: FromPath[int]) -> dict:
    found = store.get(item_id)
    if found is None:
        raise ApiError(404, "not_found", f"item {item_id} not found")
    return found


@post("/items", sync_to_thread=False)
def create_item(store: Store, data: JSONBody[ItemIn]) -> dict:
    return store.create(data.name, list(data.tags))


def _provide_store(state: State) -> ItemStore:
    return state.store


def create_app(settings: Settings, store: ItemStore, tracer_provider=None) -> Litestar:
    def startup(app: Litestar) -> None:
        app.state.store.open()
        app.state.ready = True

    def shutdown(app: Litestar) -> None:
        app.state.ready = False
        app.state.store.close()

    plugins = []
    if tracer_provider is not None:
        from litestar.plugins.opentelemetry import OpenTelemetryConfig, OpenTelemetryPlugin
        plugins.append(OpenTelemetryPlugin(OpenTelemetryConfig(tracer_provider=tracer_provider)))
    return Litestar(
        route_handlers=[health, ready, metrics, hello, list_items, get_item, create_item],
        dependencies={"store": Provide(_provide_store, sync_to_thread=False)},
        exception_handlers={ApiError: _on_api_error, ValidationException: _on_validation,
                            HTTPException: _on_http, Exception: _on_unhandled},
        middleware=[RequestContextMiddleware],
        on_startup=[startup], on_shutdown=[shutdown], plugins=plugins,
        state=State({"settings": settings, "store": store, "ready": False}),
    )


# --- C11 tracing ---------------------------------------------------------------------------------------------------
def setup_tracing(exporter=None):
    """A tracer provider when OTEL_EXPORTER_OTLP_ENDPOINT is set (or an exporter is given); None otherwise. Pass it
    to create_app, which adds Litestar's OpenTelemetry plugin (plugins are set when the app is built)."""
    if exporter is None and not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


def serve() -> Litestar:
    """The app uvicorn serves (`uvicorn --factory main:serve`): config validated, tracing set up from env."""
    return create_app(Settings.from_env(), store_from_env(), tracer_provider=setup_tracing())
