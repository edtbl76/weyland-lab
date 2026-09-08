"""Golden path — Python / Django (B153).

Blessed paved-road Django service, single-file (settings configured inline) so it stays a minimal
template. Runnable · ephemeral · extendable. Conforms to the golden-path contract
(docs/design/golden-paths.md): GET /health · /ready · /metrics · /hello. WSGI, served by gunicorn.

Django is the full-framework Python option (ORM/admin available when a real service needs them). Scaffold
FROM it: scripts/new-service.sh python/django <your-service>.
"""
import logging

import django
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

SERVICE_NAME = "golden-python-django"

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"' + SERVICE_NAME + '","msg":"%(message)s"}')
log = logging.getLogger(SERVICE_NAME)

if not settings.configured:
    settings.configure(
        DEBUG=False,
        ALLOWED_HOSTS=["*"],
        ROOT_URLCONF=__name__,
        SECRET_KEY="golden-path-template-not-a-secret",  # nosec B105 — a template placeholder; a scaffolded service injects a real key
        MIDDLEWARE=[],
        INSTALLED_APPS=[],
        DATABASES={},
    )
    django.setup()

_hello_hits = Counter("golden_hello_requests_total", "Calls to the demo /hello endpoint")


def health(request):
    """Liveness."""
    return JsonResponse({"status": "ok"})


def ready(request):
    """Readiness — the SMOKE-gate + Job probe."""
    return JsonResponse({"status": "ready"})


def metrics(request):
    """Prometheus exposition."""
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)


def hello(request):
    """The demo endpoint — the known payload the ephemeral Job asserts."""
    _hello_hits.inc()
    log.info("served /hello")
    return JsonResponse({"service": SERVICE_NAME, "message": "hello, weyland"})


urlpatterns = [
    path("health", health),
    path("ready", ready),
    path("metrics", metrics),
    path("hello", hello),
]

from django.core.wsgi import get_wsgi_application  # noqa: E402 — must follow settings.configure

application = get_wsgi_application()
