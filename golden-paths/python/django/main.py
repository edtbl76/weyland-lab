"""Golden path — Python / Django (B153; deep contract v2 since B261).

Blessed paved-road Django service, single-file (settings configured inline) so it stays a template. Runnable ·
ephemeral · extendable. WSGI, served by gunicorn. Scaffold FROM it: scripts/new-service.sh python/django <name>.

The minimal contract (docs/design/golden-paths.md): GET /health, /ready, /metrics, /hello.
Deep contract v2 (docs/concepts/golden-path-capabilities.md), in Django's own idiom:
  C1 routing        GET /items?limit&offset, GET /items/<int:item_id>, POST /items (DRF APIViews)
  C2 validation     DRF serializers for the body and the paging; invalid = 422 with per-field errors
  C3 errors         one envelope {"error": {"code", "message", "request_id"}}: DRF's EXCEPTION_HANDLER, handler404,
                    and a middleware's process_exception for anything unhandled (never a Django error page)
  C4 middleware     RequestContextMiddleware: X-Request-ID (echoed or generated) + one JSON access-log line
  C5 metrics        http_requests_total{route,status} + http_request_duration_seconds (route = the URL pattern)
  C6 config         Settings.from_env(): GOLDEN_GREETING validated at startup (empty refuses to start)
  C7 DI             Django has no native DI (catalog skip): the shared ItemStore is module state set by configure()
  C8 lifecycle      startup() opens the store and flips /ready (503 before); shutdown() at exit closes it
  C9 tests          django.test.Client, test_main.py
  C10 OpenAPI       catalog skip for Django
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

import django
from django.conf import settings

SERVICE_NAME = "golden-python-django"
DEFAULT_GREETING = "hello, weyland"

if not settings.configured:
    settings.configure(
        DEBUG=False,
        ALLOWED_HOSTS=["*"],
        ROOT_URLCONF=__name__,
        SECRET_KEY="golden-path-template-not-a-secret",  # nosec B105 — a template placeholder; a scaffolded service injects a real key
        MIDDLEWARE=[f"{__name__}.RequestContextMiddleware"],
        INSTALLED_APPS=[],
        DATABASES={},
        REST_FRAMEWORK={
            "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
            "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
            "DEFAULT_AUTHENTICATION_CLASSES": [],
            "DEFAULT_PERMISSION_CLASSES": [],
            "UNAUTHENTICATED_USER": None,
            "EXCEPTION_HANDLER": f"{__name__}.envelope_exception_handler",
        },
    )
    django.setup()

from django.http import HttpResponse, JsonResponse  # noqa: E402 — must follow settings.configure
from django.urls import path  # noqa: E402
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest  # noqa: E402
from rest_framework import exceptions, serializers, status  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from rest_framework.views import APIView  # noqa: E402

from items_store import InMemoryItemStore, ItemStore  # noqa: E402 — the shared store (a synced copy, B261)

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


# --- C7 + C8 the app state: the store, the config, readiness ----------------------------------------------------------
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


STATE = AppState(Settings(), InMemoryItemStore())


def configure(app_settings: Settings, store: ItemStore) -> None:
    global STATE
    STATE = AppState(app_settings, store)


def startup() -> None:
    STATE.store.open()
    STATE.ready = True


def shutdown() -> None:
    STATE.ready = False
    STATE.store.close()


# --- C3 errors -----------------------------------------------------------------------------------------------------
def _request_id(request) -> str:
    return getattr(request, "request_id", "") or request.META.get("HTTP_X_REQUEST_ID", "")


def envelope(request, status_code: int, code: str, message: str, fields: list | None = None) -> JsonResponse:
    error = {"code": code, "message": message, "request_id": _request_id(request)}
    if fields is not None:
        error["fields"] = fields
    return JsonResponse({"error": error}, status=status_code)


_DRF_CODES = {exceptions.NotFound: (404, "not_found"), exceptions.MethodNotAllowed: (405, "method_not_allowed"),
              exceptions.ParseError: (400, "bad_request")}


class ApiError(exceptions.APIException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def _fields(detail, prefix: str = "") -> list:
    """DRF's nested ValidationError detail as [{"field", "message"}], one per field."""
    out = []
    for name, errors in (detail.items() if isinstance(detail, dict) else [("", detail)]):
        messages = errors if isinstance(errors, list) else [errors]
        for m in messages:
            if isinstance(m, dict):
                out += _fields(m, f"{prefix}{name}.")
            else:
                out.append({"field": f"{prefix}{name}".rstrip("."), "message": str(m)})
    return out


def envelope_exception_handler(exc, context):
    """DRF's EXCEPTION_HANDLER: every API error becomes the envelope (validation is 422, not DRF's 400)."""
    request = context["request"]
    if isinstance(exc, ApiError):
        return envelope(request, exc.status_code, exc.code, exc.message)
    if isinstance(exc, exceptions.ValidationError):
        return envelope(request, 422, "validation_failed", "the request is invalid", _fields(exc.detail))
    for kind, (code_status, code) in _DRF_CODES.items():
        if isinstance(exc, kind):
            return envelope(request, code_status, code, str(exc.detail))
    if isinstance(exc, exceptions.APIException):
        return envelope(request, exc.status_code, "http_error", str(exc.detail))
    return None   # not an API exception: RequestContextMiddleware.process_exception answers it


def handler404(request, exception=None):
    return envelope(request, 404, "not_found", f"no route for {request.path}")


# --- C4 + C5 middleware --------------------------------------------------------------------------------------------
class RequestContextMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.META.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed = time.perf_counter() - started
        response["X-Request-ID"] = request.request_id
        match = getattr(request, "resolver_match", None)
        route = match.route if match else "unmatched"
        _requests.labels(route=route, status=str(response.status_code)).inc()
        _latency.labels(route=route).observe(elapsed)
        access_log.info(json.dumps({"method": request.method, "path": request.path, "status": response.status_code,
                                    "request_id": request.request_id, "duration_ms": round(elapsed * 1000, 3)}))
        return response

    def process_exception(self, request, exc):
        log.exception("unhandled error")          # the detail goes to the log, never to the client
        return envelope(request, 500, "internal", "internal error")


# --- C2 serializers + C1 views ---------------------------------------------------------------------------------------
class ItemIn(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=64, allow_blank=False)
    tags = serializers.ListField(child=serializers.CharField(), max_length=5, required=False, default=list)


class Paging(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    offset = serializers.IntegerField(min_value=0, default=0)


def health(request):
    """Liveness."""
    return JsonResponse({"status": "ok"})


def ready(request):
    """Readiness — 503 until startup() has opened the store (the SMOKE-gate + Job probe)."""
    if not STATE.ready:
        return envelope(request, 503, "not_ready", "the service is starting")
    return JsonResponse({"status": "ready"})


def metrics(request):
    """Prometheus exposition."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


def hello(request):
    """The demo endpoint — the greeting is config (C6)."""
    _hello_hits.inc()
    return JsonResponse({"service": SERVICE_NAME, "message": STATE.settings.greeting})


class ItemsView(APIView):
    def get(self, request):
        paging = Paging(data=request.query_params)
        paging.is_valid(raise_exception=True)
        limit, offset = paging.validated_data["limit"], paging.validated_data["offset"]
        return Response({"items": STATE.store.list(limit, offset), "limit": limit, "offset": offset})

    def post(self, request):
        body = ItemIn(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(STATE.store.create(body.validated_data["name"], body.validated_data["tags"]),
                        status=status.HTTP_201_CREATED)


class ItemView(APIView):
    def get(self, request, item_id: int):
        found = STATE.store.get(item_id)
        if found is None:
            raise ApiError(404, "not_found", f"item {item_id} not found")
        return Response(found)


urlpatterns = [
    path("health", health),
    path("ready", ready),
    path("metrics", metrics),
    path("hello", hello),
    path("items", ItemsView.as_view()),
    path("items/<int:item_id>", ItemView.as_view()),
]


# --- C11 tracing ---------------------------------------------------------------------------------------------------
def setup_tracing(exporter=None):
    """OTel spans per request when OTEL_EXPORTER_OTLP_ENDPOINT is set (or an exporter is given); else a no-op.
    Returns the tracer provider, or None when tracing is off. Call before the WSGI handler loads its middleware."""
    if exporter is None and not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    DjangoInstrumentor().instrument(tracer_provider=provider)
    return provider


def serve():
    """The WSGI application gunicorn serves: config validated, tracing set up, the store opened, then requests."""
    from django.core.wsgi import get_wsgi_application
    configure(Settings.from_env(), store_from_env())
    setup_tracing()
    startup()
    atexit.register(shutdown)
    return get_wsgi_application()
