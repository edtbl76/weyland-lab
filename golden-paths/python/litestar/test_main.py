"""Golden-path self-test (Python/Litestar) — the minimal contract AND deep contract v2 (B153, B261).

Litestar's TestClient drives every row of the deep contract (docs/concepts/golden-path-capabilities.md): C1 routing,
C2 msgspec structs + Parameter constraints, C3 the error envelope (exception handlers), C4/C5 an ASGI middleware, C6
validated config, C7 the shared store through `Provide`, C8 on_startup/on_shutdown gating /ready, C10 OpenAPI, C11
tracing through Litestar's OpenTelemetry plugin.
"""
import json
import logging

import pytest
from litestar.testing import TestClient

import main
from main import InMemoryItemStore, Settings, create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings(greeting="hello, weyland"), InMemoryItemStore())) as c:
        yield c


# --- the minimal contract ---------------------------------------------------------------------------------------
def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_ready_is_ready_after_startup(client):
    assert client.get("/ready").json()["status"] == "ready"


def test_hello_returns_the_known_payload(client):
    assert client.get("/hello").json() == {"service": "golden-python-litestar", "message": "hello, weyland"}


def test_metrics_exposes_prometheus(client):
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200 and "golden_hello_requests_total" in r.text


# --- C1 routing + C7 the store ------------------------------------------------------------------------------------
def test_create_then_get_then_list(client):
    created = client.post("/items", json={"name": "widget", "tags": ["a", "b"]})
    assert created.status_code == 201
    item = created.json()
    assert item["name"] == "widget" and item["tags"] == ["a", "b"] and isinstance(item["id"], int)
    assert client.get(f"/items/{item['id']}").json() == item
    assert client.get("/items").json() == {"items": [item], "limit": 20, "offset": 0}


def test_list_honours_limit_and_offset(client):
    for n in range(5):
        client.post("/items", json={"name": f"n{n}"})
    assert [i["name"] for i in client.get("/items", params={"limit": 2, "offset": 1}).json()["items"]] == ["n1", "n2"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "x"}])
def test_list_rejects_out_of_range_paging(client, params):
    r = client.get("/items", params=params)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_the_store_is_provided_and_replaceable():
    store = InMemoryItemStore()
    with TestClient(create_app(Settings(greeting="hi"), store)) as c:
        c.post("/items", json={"name": "x"})
    assert [i["name"] for i in store.list(10, 0)] == ["x"]


# --- C2 validation + C3 the error envelope ----------------------------------------------------------------------
@pytest.mark.parametrize("body,field", [({"name": ""}, "name"), ({"name": "x" * 65}, "name"),
                                        ({"name": "ok", "tags": ["t"] * 6}, "tags"), ({}, "name")])
def test_invalid_bodies_are_422_with_field_errors(client, body, field):
    r = client.post("/items", json=body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_failed" and err["request_id"]
    assert any(f["field"] == field for f in err["fields"])


def test_an_invalid_tag_names_its_position(client):
    r = client.post("/items", json={"name": "ok", "tags": ["fine", 7]})
    assert [f["field"] for f in r.json()["error"]["fields"]] == ["tags.1"]


def test_malformed_json_is_a_400_envelope(client):
    r = client.post("/items", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"


def test_unknown_item_is_a_404_envelope(client):
    r = client.get("/items/999999")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "item 999999 not found",
                                  "request_id": r.headers["x-request-id"]}}


def test_litestars_own_errors_use_the_envelope_too(client):
    unknown = client.get("/nope")
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "not_found"
    wrong = client.delete("/items")
    assert wrong.status_code == 405 and wrong.json()["error"]["code"] == "method_not_allowed"


def test_an_unhandled_exception_is_a_500_envelope_not_a_framework_page(monkeypatch):
    store = InMemoryItemStore()

    def boom(*_a, **_k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(store, "list", boom)
    with TestClient(create_app(Settings(greeting="hi"), store)) as c:
        r = c.get("/items")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal" and "kaboom" not in r.text


# --- C4 request id + access log, C5 metrics ----------------------------------------------------------------------
def test_a_request_id_is_echoed_or_generated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    assert len(client.get("/health").headers["x-request-id"]) >= 16


def test_one_json_access_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="golden-python-litestar.access"):
        client.get("/items/42", headers={"X-Request-ID": "rid-1"})
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name.endswith(".access")]
    assert len(lines) == 1 and lines[0]["duration_ms"] >= 0
    assert {k: lines[0][k] for k in ("method", "path", "status", "request_id")} == \
        {"method": "GET", "path": "/items/42", "status": 404, "request_id": "rid-1"}


def test_requests_are_counted_per_route_template_and_status(client):
    client.get("/items/1")
    text = client.get("/metrics").text
    assert 'http_requests_total{route="/items/{item_id}",status="404"}' in text
    assert "http_request_duration_seconds_bucket" in text


# --- C6 config, C8 lifecycle ---------------------------------------------------------------------------------------
def test_greeting_comes_from_config():
    with TestClient(create_app(Settings(greeting="hola"), InMemoryItemStore())) as c:
        assert c.get("/hello").json()["message"] == "hola"


def test_an_empty_greeting_fails_at_startup_not_later(monkeypatch):
    monkeypatch.setenv("GOLDEN_GREETING", "")
    with pytest.raises(ValueError, match="GOLDEN_GREETING"):
        Settings.from_env()


def test_the_default_greeting_when_unset(monkeypatch):
    monkeypatch.delenv("GOLDEN_GREETING", raising=False)
    assert Settings.from_env().greeting == "hello, weyland"


def test_ready_is_503_before_startup_and_shutdown_closes_the_store():
    store = InMemoryItemStore()
    app = create_app(Settings(greeting="hi"), store)
    r = TestClient(app).get("/ready")                  # no `with`: the startup hooks have not run
    assert r.status_code == 503 and r.json()["error"]["code"] == "not_ready"
    with TestClient(app):
        assert not store.closed
    assert store.closed


def test_the_real_backends_are_chosen_by_env_without_connecting(monkeypatch):
    monkeypatch.setenv("GOLDEN_DATABASE_URL", "postgresql://u:p@db.invalid:5432/x")
    monkeypatch.delenv("GOLDEN_VALKEY_URL", raising=False)
    monkeypatch.delenv("GOLDEN_KAFKA_BOOTSTRAP", raising=False)
    assert type(main.store_from_env()).__name__ == "PostgresItemStore"
    monkeypatch.delenv("GOLDEN_DATABASE_URL")
    assert type(main.store_from_env()).__name__ == "InMemoryItemStore"


def test_serve_builds_the_app_from_env(monkeypatch):
    monkeypatch.delenv("GOLDEN_DATABASE_URL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("GOLDEN_GREETING", "served")
    with TestClient(main.serve()) as c:
        assert c.get("/hello").json()["message"] == "served"


# --- C10 OpenAPI, C11 tracing ---------------------------------------------------------------------------------------
def test_openapi_describes_the_items_api(client):
    spec = client.get("/schema/openapi.json").json()
    assert {"/items", "/items/{item_id}"} <= set(spec["paths"])


def test_tracing_is_a_no_op_without_an_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert main.setup_tracing() is None


def test_tracing_emits_a_span_per_request_when_enabled():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    provider = main.setup_tracing(exporter=exporter)
    with TestClient(create_app(Settings(greeting="hi"), InMemoryItemStore(), tracer_provider=provider)) as c:
        c.get("/hello")
    assert any("hello" in s.name for s in exporter.get_finished_spans())


def test_tracing_exports_over_otlp_when_the_endpoint_is_set(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    provider = main.setup_tracing()
    try:
        processor = provider._active_span_processor._span_processors[0]
        assert type(processor).__name__ == "BatchSpanProcessor"
        assert type(processor.span_exporter).__name__ == "OTLPSpanExporter"
    finally:
        provider.shutdown()


def test_the_middleware_passes_non_http_traffic_through_untouched():
    import asyncio
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])
    asyncio.run(main.RequestContextMiddleware(inner)({"type": "websocket"}, None, None))
    assert seen == ["websocket"]
