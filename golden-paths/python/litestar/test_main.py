"""Golden-path self-test (Python/Litestar) — the lane probe + contract proof. Litestar TestClient."""
from litestar.testing import TestClient

from main import app

client = TestClient(app=app)


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
    assert body["service"] == "golden-python-litestar"


def test_metrics_exposes_prometheus():
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "golden_hello_requests_total" in r.text
