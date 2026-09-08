"""Golden-path self-test (Python/FastAPI) — the lane's build-infra probe + the contract's proof.

Exercises the full golden-path contract via FastAPI's TestClient: liveness, readiness, metrics, and the
demo endpoint's known payload. Replaces the B88 python hello fixture — one artifact that is both the
blessed template and the CI probe.
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


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
    assert body["service"] == "golden-python-fastapi"


def test_metrics_exposes_prometheus():
    client.get("/hello")  # increment the counter first
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "golden_hello_requests_total" in r.text
