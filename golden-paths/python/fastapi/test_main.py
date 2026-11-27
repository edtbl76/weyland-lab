"""Golden-path self-test (Python/FastAPI) — the minimal contract AND deep contract v2 (B153, B260).

Exercises every row of the deep contract (docs/concepts/golden-path-capabilities.md) through FastAPI's own
TestClient: C1 routing, C2 validation, C3 the error envelope, C4 request-id + access-log middleware, C5 per-route
metrics, C6 validated config, C7 the injected ItemStore, C8 lifespan-gated readiness, C10 OpenAPI, C11 tracing.
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient

import main
from main import InMemoryItemStore, Settings, create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(greeting="hello, weyland"))) as c:  # `with` runs the lifespan (C8)
        yield c


# --- the minimal contract (unchanged) ---------------------------------------------------------------------
def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_is_ready_after_startup(client):
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready"


def test_hello_returns_the_known_payload(client):
    body = client.get("/hello").json()
    assert body == {"service": "golden-python-fastapi", "message": "hello, weyland"}


def test_metrics_exposes_prometheus(client):
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200 and "golden_hello_requests_total" in r.text


# --- C1 routing + C7 the injected store ---------------------------------------------------------------------
def test_create_then_get_then_list(client):
    created = client.post("/items", json={"name": "widget", "tags": ["a", "b"]})
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "widget" and item["tags"] == ["a", "b"] and isinstance(item["id"], int)
    assert client.get(f"/items/{item['id']}").json() == item
    listed = client.get("/items").json()
    assert listed["items"] == [item] and listed["limit"] == 20 and listed["offset"] == 0


def test_list_honours_limit_and_offset(client):
    for n in range(5):
        client.post("/items", json={"name": f"n{n}"})
    page = client.get("/items", params={"limit": 2, "offset": 1}).json()
    assert [i["name"] for i in page["items"]] == ["n1", "n2"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
def test_list_rejects_out_of_range_paging(client, params):
    r = client.get("/items", params=params)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_the_store_is_injected_and_replaceable():
    store = InMemoryItemStore()
    app = create_app(Settings(greeting="hi"), store=store)
    with TestClient(app) as c:
        c.post("/items", json={"name": "x"})
    assert [i["name"] for i in store.list(10, 0)] == ["x"]     # the shared, framework-neutral store (B261)


# --- C2 validation + C3 the error envelope -------------------------------------------------------------------
@pytest.mark.parametrize("body,field", [({"name": ""}, "name"), ({"name": "x" * 65}, "name"),
                                        ({"name": "ok", "tags": ["t"] * 6}, "tags"), ({}, "name")])
def test_invalid_bodies_are_422_with_field_errors(client, body, field):
    r = client.post("/items", json=body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_failed" and err["request_id"]
    assert any(f["field"] == field for f in err["fields"])


def test_unknown_item_is_a_404_envelope(client):
    r = client.get("/items/999999")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "item 999999 not found",
                                  "request_id": r.headers["x-request-id"]}}


def test_an_unhandled_exception_is_a_500_envelope_not_a_framework_page():
    app = create_app(Settings(greeting="hi"))

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal" and "kaboom" not in r.text   # never leak the exception


# --- C4 request id + access log ------------------------------------------------------------------------------
def test_a_request_id_is_echoed_or_generated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) >= 16


def test_one_json_access_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="golden-python-fastapi.access"):
        client.get("/items/42", headers={"X-Request-ID": "rid-1"})
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name.endswith(".access")]
    assert lines == [{"method": "GET", "path": "/items/42", "status": 404, "request_id": "rid-1",
                      "duration_ms": lines[0]["duration_ms"]}]
    assert lines[0]["duration_ms"] >= 0


# --- C5 per-route metrics -----------------------------------------------------------------------------------
def test_requests_are_counted_per_route_template_and_status(client):
    client.get("/items/1")
    text = client.get("/metrics").text
    assert 'http_requests_total{route="/items/{item_id}",status="404"}' in text
    assert "http_request_duration_seconds_bucket" in text


# --- C6 validated config ------------------------------------------------------------------------------------
def test_greeting_comes_from_config(client):
    with TestClient(create_app(Settings(greeting="hola"))) as c:
        assert c.get("/hello").json()["message"] == "hola"


def test_an_empty_greeting_fails_at_startup_not_later(monkeypatch):
    monkeypatch.setenv("GOLDEN_GREETING", "")
    with pytest.raises(ValueError, match="GOLDEN_GREETING"):
        Settings.from_env()


def test_the_default_greeting_when_unset(monkeypatch):
    monkeypatch.delenv("GOLDEN_GREETING", raising=False)
    assert Settings.from_env().greeting == "hello, weyland"


# --- C8 lifecycle --------------------------------------------------------------------------------------------
def test_ready_is_503_before_startup_completes():
    app = create_app(Settings(greeting="hi"))
    c = TestClient(app)                     # no `with`: the lifespan has not run
    r = c.get("/ready")
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_ready"


def test_shutdown_closes_the_store():
    store = InMemoryItemStore()
    with TestClient(create_app(Settings(greeting="hi"), store=store)):
        assert not store.closed
    assert store.closed


# --- C10 OpenAPI, C11 tracing ---------------------------------------------------------------------------------
def test_openapi_describes_the_items_api(client):
    spec = client.get("/openapi.json").json()
    assert {"/items", "/items/{item_id}"} <= set(spec["paths"])


def test_tracing_is_a_no_op_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert main.setup_tracing(create_app(Settings(greeting="hi"))) is None


def test_tracing_emits_a_span_per_request_when_enabled():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    app = create_app(Settings(greeting="hi"))
    assert main.setup_tracing(app, exporter=exporter) is not None
    with TestClient(app) as c:
        c.get("/hello")
    assert any("/hello" in s.name for s in exporter.get_finished_spans())


def test_the_frameworks_own_http_errors_use_the_envelope_too(client):
    # C3: an unknown route or a wrong method is still the envelope, never FastAPI's default {"detail": ...}.
    unknown = client.get("/nope")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "not_found"
    wrong = client.delete("/items")
    assert wrong.status_code == 405 and wrong.json()["error"]["code"] == "method_not_allowed"
    assert wrong.headers["x-request-id"] == wrong.json()["error"]["request_id"]


def test_tracing_exports_over_otlp_when_the_endpoint_is_set(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    provider = main.setup_tracing(create_app(Settings(greeting="hi")))
    try:
        processor = provider._active_span_processor._span_processors[0]
        assert type(processor).__name__ == "BatchSpanProcessor"
        assert type(processor.span_exporter).__name__ == "OTLPSpanExporter"
    finally:
        provider.shutdown()


def test_the_real_backends_are_chosen_by_env_without_connecting(monkeypatch):
    # C7: GOLDEN_DATABASE_URL selects the shared Postgres-backed store; it connects only when the lifespan opens it.
    monkeypatch.setenv("GOLDEN_DATABASE_URL", "postgresql://u:p@db.invalid:5432/x")
    monkeypatch.delenv("GOLDEN_VALKEY_URL", raising=False)
    monkeypatch.delenv("GOLDEN_KAFKA_BOOTSTRAP", raising=False)
    assert type(main.store_from_env()).__name__ == "PostgresItemStore"
    monkeypatch.delenv("GOLDEN_DATABASE_URL")
    assert type(main.store_from_env()).__name__ == "InMemoryItemStore"
