"""Golden-path self-test (Python/Flask) — the lane probe + contract proof. Flask test client."""
from main import app

client = app.test_client()


def test_health_is_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_ready_is_ready():
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ready"


def test_hello_returns_the_known_payload():
    r = client.get("/hello")
    assert r.status_code == 200
    body = r.get_json()
    assert body["message"] == "hello, weyland"
    assert body["service"] == "golden-python-flask"


def test_metrics_exposes_prometheus():
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"golden_hello_requests_total" in r.data
