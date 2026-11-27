"""Golden-path self-test (Python/Flask) — the minimal contract AND deep contract v2 (B153, B261).

Flask's test client drives every row of the deep contract (docs/concepts/golden-path-capabilities.md): C1 routing, C2
marshmallow schemas, C3 the error envelope (errorhandlers), C4/C5 before/after_request, C6 validated config, C7 the
shared store on the app (Flask has no native DI: recorded), C8 the factory opens the store and gates /ready, C11
tracing. C10 (OpenAPI) is a catalog skip for Flask.
"""
import json
import logging

import pytest

import main
from main import InMemoryItemStore, Settings, create_app


@pytest.fixture
def app():
    application = create_app(Settings(greeting="hello, weyland"), InMemoryItemStore())
    yield application
    main.app_shutdown(application)


@pytest.fixture
def client(app):
    return app.test_client()


# --- the minimal contract ---------------------------------------------------------------------------------------
def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_ready_is_ready_after_startup(client):
    assert client.get("/ready").get_json()["status"] == "ready"


def test_hello_returns_the_known_payload(client):
    assert client.get("/hello").get_json() == {"service": "golden-python-flask", "message": "hello, weyland"}


def test_metrics_exposes_prometheus(client):
    client.get("/hello")
    r = client.get("/metrics")
    assert r.status_code == 200 and "golden_hello_requests_total" in r.get_data(as_text=True)


# --- C1 routing + C7 the store ------------------------------------------------------------------------------------
def test_create_then_get_then_list(client):
    created = client.post("/items", json={"name": "widget", "tags": ["a", "b"]})
    assert created.status_code == 201
    item = created.get_json()
    assert item["name"] == "widget" and item["tags"] == ["a", "b"] and isinstance(item["id"], int)
    assert client.get(f"/items/{item['id']}").get_json() == item
    assert client.get("/items").get_json() == {"items": [item], "limit": 20, "offset": 0}


def test_list_honours_limit_and_offset(client):
    for n in range(5):
        client.post("/items", json={"name": f"n{n}"})
    assert [i["name"] for i in client.get("/items?limit=2&offset=1").get_json()["items"]] == ["n1", "n2"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=x"])
def test_list_rejects_out_of_range_paging(client, query):
    r = client.get(f"/items?{query}")
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "validation_failed"


def test_the_store_is_the_one_the_factory_was_given():
    store = InMemoryItemStore()
    application = create_app(Settings(greeting="hi"), store)
    application.test_client().post("/items", json={"name": "x"})
    main.app_shutdown(application)
    assert [i["name"] for i in store.list(10, 0)] == ["x"]


# --- C2 validation + C3 the error envelope ----------------------------------------------------------------------
@pytest.mark.parametrize("body,field", [({"name": ""}, "name"), ({"name": "x" * 65}, "name"),
                                        ({"name": "ok", "tags": ["t"] * 6}, "tags"), ({}, "name")])
def test_invalid_bodies_are_422_with_field_errors(client, body, field):
    r = client.post("/items", json=body)
    assert r.status_code == 422
    err = r.get_json()["error"]
    assert err["code"] == "validation_failed" and err["request_id"]
    assert any(f["field"] == field for f in err["fields"])


def test_an_invalid_tag_names_its_position(client):
    r = client.post("/items", json={"name": "ok", "tags": ["fine", 7]})
    assert [f["field"] for f in r.get_json()["error"]["fields"]] == ["tags.1"]


def test_malformed_json_is_a_400_envelope(client):
    r = client.post("/items", data="{not json", content_type="application/json")
    assert r.status_code == 400 and r.get_json()["error"]["code"] == "bad_request"


def test_unknown_item_is_a_404_envelope(client):
    r = client.get("/items/999999")
    assert r.status_code == 404
    assert r.get_json() == {"error": {"code": "not_found", "message": "item 999999 not found",
                                      "request_id": r.headers["X-Request-ID"]}}


def test_flasks_own_errors_use_the_envelope_too(client):
    unknown = client.get("/nope")
    assert unknown.status_code == 404 and unknown.get_json()["error"]["code"] == "not_found"
    wrong = client.delete("/items")
    assert wrong.status_code == 405 and wrong.get_json()["error"]["code"] == "method_not_allowed"


def test_an_unhandled_exception_is_a_500_envelope_not_a_flask_page(app, client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(app.extensions["golden"].store, "list", boom)
    r = client.get("/items")
    assert r.status_code == 500 and r.get_json()["error"]["code"] == "internal"
    assert "kaboom" not in r.get_data(as_text=True)


# --- C4 request id + access log, C5 metrics ----------------------------------------------------------------------
def test_a_request_id_is_echoed_or_generated(client):
    assert client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"] == "abc-123"
    assert len(client.get("/health").headers["X-Request-ID"]) >= 16


def test_one_json_access_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="golden-python-flask.access"):
        client.get("/items/42", headers={"X-Request-ID": "rid-1"})
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name.endswith(".access")]
    assert len(lines) == 1 and lines[0]["duration_ms"] >= 0
    assert {k: lines[0][k] for k in ("method", "path", "status", "request_id")} == \
        {"method": "GET", "path": "/items/42", "status": 404, "request_id": "rid-1"}


def test_requests_are_counted_per_route_template_and_status(client):
    client.get("/items/1")
    text = client.get("/metrics").get_data(as_text=True)
    assert 'http_requests_total{route="/items/<int:item_id>",status="404"}' in text
    assert "http_request_duration_seconds_bucket" in text


# --- C6 config, C8 lifecycle ---------------------------------------------------------------------------------------
def test_greeting_comes_from_config():
    application = create_app(Settings(greeting="hola"), InMemoryItemStore())
    assert application.test_client().get("/hello").get_json()["message"] == "hola"
    main.app_shutdown(application)


def test_an_empty_greeting_fails_at_startup_not_later(monkeypatch):
    monkeypatch.setenv("GOLDEN_GREETING", "")
    with pytest.raises(ValueError, match="GOLDEN_GREETING"):
        Settings.from_env()


def test_the_default_greeting_when_unset(monkeypatch):
    monkeypatch.delenv("GOLDEN_GREETING", raising=False)
    assert Settings.from_env().greeting == "hello, weyland"


def test_ready_is_503_until_the_store_is_open_and_shutdown_closes_it():
    store = InMemoryItemStore()
    application = create_app(Settings(greeting="hi"), store, start=False)
    r = application.test_client().get("/ready")
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "not_ready"
    main.app_startup(application)
    assert application.test_client().get("/ready").status_code == 200
    main.app_shutdown(application)
    assert store.closed


def test_the_real_backends_are_chosen_by_env_without_connecting(monkeypatch):
    monkeypatch.setenv("GOLDEN_DATABASE_URL", "postgresql://u:p@db.invalid:5432/x")
    monkeypatch.delenv("GOLDEN_VALKEY_URL", raising=False)
    monkeypatch.delenv("GOLDEN_KAFKA_BOOTSTRAP", raising=False)
    assert type(main.store_from_env()).__name__ == "PostgresItemStore"
    monkeypatch.delenv("GOLDEN_DATABASE_URL")
    assert type(main.store_from_env()).__name__ == "InMemoryItemStore"


def test_serve_validates_config_opens_the_store_and_returns_the_app(monkeypatch):
    monkeypatch.delenv("GOLDEN_DATABASE_URL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setenv("GOLDEN_GREETING", "served")
    application = main.serve()
    try:
        assert application.test_client().get("/hello").get_json()["message"] == "served"
    finally:
        main.app_shutdown(application)


# --- C11 tracing ---------------------------------------------------------------------------------------------------
def test_tracing_is_a_no_op_without_an_endpoint(app, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert main.setup_tracing(app) is None


def test_tracing_emits_a_span_per_request_when_enabled():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    application = create_app(Settings(greeting="hi"), InMemoryItemStore())
    assert main.setup_tracing(application, exporter=exporter) is not None
    application.test_client().get("/hello")
    assert any("hello" in s.name for s in exporter.get_finished_spans())
    main.app_shutdown(application)


def test_tracing_exports_over_otlp_when_the_endpoint_is_set(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    application = create_app(Settings(greeting="hi"), InMemoryItemStore())
    provider = main.setup_tracing(application)
    try:
        processor = provider._active_span_processor._span_processors[0]
        assert type(processor).__name__ == "BatchSpanProcessor"
        assert type(processor.span_exporter).__name__ == "OTLPSpanExporter"
    finally:
        provider.shutdown()
        main.app_shutdown(application)
