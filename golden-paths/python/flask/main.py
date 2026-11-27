"""Golden path — Python / Flask (B153; deep contract v2 since B261).

Blessed paved-road Flask service. Runnable · ephemeral · extendable. WSGI, served by gunicorn (`main:serve()`).
Scaffold FROM it: scripts/new-service.sh python/flask <your-service>.

The minimal contract (docs/design/golden-paths.md): GET /health, /ready, /metrics, /hello.
Deep contract v2 (docs/concepts/golden-path-capabilities.md), in Flask's own idiom:
  C1 routing        GET /items?limit&offset, GET /items/<int:item_id>, POST /items
  C2 validation     marshmallow schemas for the body and the paging (Flask has none native); invalid = 422 with fields
  C3 errors         one envelope {"error": {"code", "message", "request_id"}} from errorhandlers (HTTP, validation,
                    anything unhandled) — never a Flask/Werkzeug error page
  C4 middleware     before_request / after_request: X-Request-ID (echoed or generated) + one JSON access-log line
  C5 metrics        http_requests_total{route,status} + http_request_duration_seconds (route = the URL rule)
  C6 config         Settings.from_env(): GOLDEN_GREETING validated at startup (empty refuses to start)
  C7 DI             Flask has no native DI (catalog skip): the shared ItemStore lives on app.extensions["golden"]
  C8 lifecycle      the app factory opens the store and flips /ready (503 before); app_shutdown() closes it
  C9 tests          Flask's test client, test_main.py
  C10 OpenAPI       catalog skip for Flask
  C11 tracing       setup_tracing(): OTel spans per request when OTEL_EXPORTER_OTLP_ENDPOINT is set; else a no-op
"""
from __future__ import annotations

import atexit
import dataclasses
import json
import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request
from marshmallow import Schema, ValidationError, fields, validate
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from werkzeug.exceptions import HTTPException

from items_store import InMemoryItemStore, ItemStore  # the shared store (a synced copy, B261)

SERVICE_NAME = "golden-python-flask"
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


# --- C7 + C8 the app state ------------------------------------------------------------------------------------------
@dataclasses.dataclass
class AppState:
    settings: Settings
    store: ItemStore
    ready: bool = False


def store_from_env() -> ItemStore:
    """GOLDEN_DATABASE_URL selects the shared real backends; the in-memory store otherwise (nothing connects here)."""
    if not os.environ.get("GOLDEN_DATABASE_URL"):
        return InMemoryItemStore()
    import items_backends
    return items_backends.build_store_from_env()


def _state() -> AppState:
    from flask import current_app
    return current_app.extensions["golden"]


def app_startup(app: Flask) -> None:
    app.extensions["golden"].store.open()
    app.extensions["golden"].ready = True


def app_shutdown(app: Flask) -> None:
    app.extensions["golden"].ready = False
    app.extensions["golden"].store.close()


# --- C2 schemas ----------------------------------------------------------------------------------------------------
class ItemIn(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=64))
    tags = fields.List(fields.String(), load_default=list, validate=validate.Length(max=5))


class Paging(Schema):
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))


# --- C3 errors -----------------------------------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


_HTTP_CODES = {400: "bad_request", 404: "not_found", 405: "method_not_allowed"}


def envelope(status: int, code: str, message: str, fields_: list | None = None):
    error = {"code": code, "message": message, "request_id": getattr(g, "request_id", "")}
    if fields_ is not None:
        error["fields"] = fields_
    return jsonify({"error": error}), status


def _fields(messages, prefix: str = "") -> list:
    """marshmallow's nested error messages as [{"field", "message"}], one per message."""
    out = []
    for name, errors in messages.items():
        if isinstance(errors, dict):
            out += _fields(errors, f"{prefix}{name}.")
        else:
            out += [{"field": f"{prefix}{name}", "message": str(m)} for m in errors]
    return out


def _install_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def api_error(exc: ApiError):
        return envelope(exc.status, exc.code, exc.message)

    @app.errorhandler(ValidationError)
    def validation_error(exc: ValidationError):
        return envelope(422, "validation_failed", "the request is invalid", _fields(exc.messages))

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        return envelope(exc.code, _HTTP_CODES.get(exc.code, "http_error"), exc.description)

    @app.errorhandler(Exception)
    def unhandled(exc: Exception):
        log.exception("unhandled error")          # the detail goes to the log, never to the client
        return envelope(500, "internal", "internal error")


# --- C4 + C5 middleware --------------------------------------------------------------------------------------------
def _install_middleware(app: Flask) -> None:
    @app.before_request
    def request_context():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        g.started = time.perf_counter()

    @app.after_request
    def access(response):
        elapsed = time.perf_counter() - g.started
        response.headers["X-Request-ID"] = g.request_id
        route = request.url_rule.rule if request.url_rule else "unmatched"
        _requests.labels(route=route, status=str(response.status_code)).inc()
        _latency.labels(route=route).observe(elapsed)
        access_log.info(json.dumps({"method": request.method, "path": request.path, "status": response.status_code,
                                    "request_id": g.request_id, "duration_ms": round(elapsed * 1000, 3)}))
        return response


# --- C1 routes -----------------------------------------------------------------------------------------------------
def _install_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        """Liveness."""
        return jsonify(status="ok")

    @app.get("/ready")
    def ready():
        """Readiness — 503 until the store is open (the SMOKE-gate + Job probe)."""
        if not _state().ready:
            raise ApiError(503, "not_ready", "the service is starting")
        return jsonify(status="ready")

    @app.get("/metrics")
    def metrics():
        """Prometheus exposition."""
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.get("/hello")
    def hello():
        """The demo endpoint — the greeting is config (C6)."""
        _hello_hits.inc()
        return jsonify(service=SERVICE_NAME, message=_state().settings.greeting)

    @app.get("/items")
    def list_items():
        paging = Paging().load(request.args)
        return jsonify(items=_state().store.list(paging["limit"], paging["offset"]),
                       limit=paging["limit"], offset=paging["offset"])

    @app.get("/items/<int:item_id>")
    def get_item(item_id: int):
        found = _state().store.get(item_id)
        if found is None:
            raise ApiError(404, "not_found", f"item {item_id} not found")
        return jsonify(found)

    @app.post("/items")
    def create_item():
        body = ItemIn().load(request.get_json())
        return jsonify(_state().store.create(body["name"], body["tags"])), 201


def create_app(settings: Settings, store: ItemStore, start: bool = True) -> Flask:
    """The app factory: config, the store, the handlers; `start` opens the store (C8)."""
    app = Flask(SERVICE_NAME)
    app.extensions["golden"] = AppState(settings, store)
    _install_error_handlers(app)
    _install_middleware(app)
    _install_routes(app)
    if start:
        app_startup(app)
    return app


# --- C11 tracing ---------------------------------------------------------------------------------------------------
def setup_tracing(app: Flask, exporter=None):
    """OTel spans per request when OTEL_EXPORTER_OTLP_ENDPOINT is set (or an exporter is given); else a no-op.
    Returns the tracer provider, or None when tracing is off."""
    if exporter is None and not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    FlaskInstrumentor().instrument_app(app, tracer_provider=provider)
    return provider


def serve() -> Flask:
    """The WSGI app gunicorn serves: config validated, the store opened, tracing set up, shutdown at exit."""
    app = create_app(Settings.from_env(), store_from_env())
    setup_tracing(app)
    atexit.register(app_shutdown, app)
    return app
