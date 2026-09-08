"""Golden-path self-test (Python/Django) — the lane probe + contract proof.

Importing `main` configures Django settings inline; the Django test Client then drives the four
contract routes. No pytest-django needed — settings are configured at import.
"""
import main  # noqa: F401 — importing configures Django settings + urls before Client is used
from django.test import Client

client = Client()


def test_health_is_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_is_ready():
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_hello_returns_the_known_payload():
    r = client.get("/hello")
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "hello, weyland"
    assert body["service"] == "golden-python-django"


def test_metrics_exposes_prometheus():
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"golden_hello_requests_total" in r.content
