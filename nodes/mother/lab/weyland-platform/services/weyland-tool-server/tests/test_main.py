"""Tests for the weyland-tool-server FastAPI app + its helpers.

Every assertion checks a REAL outcome — the HTTP status/body a client would get, the string a formatter produces,
the Verdict the guard returns, the fail-open error dict a backend check returns — not that a mock was called.
Backends (pg/qdrant/weaviate/neo4j/ollama/dagster) are stubbed per-test to a fixture value, and we assert how the
handler SHAPES that into its response. The live store/LLM round-trips are validated in the running system.
"""
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import main
from guardrails.verdict import Decision, Hook


@pytest.fixture
def client():
    # No context manager on purpose: the lifespan builds OnnxBge (loads an ONNX model that isn't present in
    # tests). Constructing TestClient without `with` skips lifespan, leaving embed_model=None (the real
    # "model not loaded yet" state), which /ready and /status are supposed to handle.
    return TestClient(main.app)


# ── pure formatters ──────────────────────────────────────────────────────────────────────────────
def test_to_vector_formats_floats_in_pgvector_literal():
    assert main._to_vector([1, 2, 3]) == "[1.0,2.0,3.0]"
    assert main._to_vector([0.5, -1]) == "[0.5,-1.0]"
    assert main._to_vector([]) == "[]"


def test_build_context_numbers_and_source_tags_chunks():
    ctx = main._build_context([
        {"source": "a.md", "chunk_index": 0, "content": "alpha"},
        {"source": "b.md", "chunk_index": 4, "content": "beta"},
    ])
    assert ctx == "[1] source: a.md (chunk 0)\nalpha\n\n[2] source: b.md (chunk 4)\nbeta"


def test_build_context_empty_is_empty_string():
    assert main._build_context([]) == ""


def test_actor_reads_only_the_trusted_gateway_header():
    assert main._actor("consumer-x") == "consumer-x"
    assert main._actor(None) is None


# ── validate_required_secrets ──────────────────────────────────────────────────────────────────────
def test_validate_required_secrets_raises_when_missing(monkeypatch):
    monkeypatch.setattr(main, "PG_PASSWORD", "")
    monkeypatch.setattr(main, "NEO4J_PASSWORD", "")
    with pytest.raises(RuntimeError) as exc:
        main.validate_required_secrets()
    assert "WEYLAND_DB_PASSWORD" in str(exc.value) and "NEO4J_PASSWORD" in str(exc.value)


def test_validate_required_secrets_passes_when_present(monkeypatch):
    monkeypatch.setattr(main, "PG_PASSWORD", "x")
    monkeypatch.setattr(main, "NEO4J_PASSWORD", "y")
    main.validate_required_secrets()  # no raise


# ── _guard (fail-open POST to weyland-guard) ─────────────────────────────────────────────────────────
class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_guard_returns_block_verdict_when_guard_blocks(monkeypatch):
    monkeypatch.setattr(main.httpx, "post",
                        lambda *a, **k: _Resp({"decision": "block",
                                               "verdict": {"validator": "pii", "reason": "leak", "score": 0.9}}))
    v = main._guard(Hook.INPUT, "req-1", {"query": "q"}, "actor-1")
    assert v is not None
    assert v.validator == "pii" and v.decision == Decision.BLOCK and v.reason == "leak"


def test_guard_allows_when_decision_not_block(monkeypatch):
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _Resp({"decision": "allow"}))
    assert main._guard(Hook.INPUT, "req-2", {"query": "q"}) is None


def test_guard_fails_open_on_transport_error(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("guard down")
    monkeypatch.setattr(main.httpx, "post", _boom)
    assert main._guard(Hook.OUTPUT, "req-3", {"answer": "a"}) is None   # outage => allow, never "no answer"


# ── backend health checks (fail-open error dicts + ok shaping) ───────────────────────────────────────
def test_check_ollama_ok_lists_models(monkeypatch):
    class _R:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"id": "m1"}, {"id": "m2"}]}
    monkeypatch.setattr(main.httpx, "get", lambda *a, **k: _R())
    assert main._check_ollama() == {"status": "ok", "models": ["m1", "m2"]}


def test_check_ollama_error_is_failopen_dict(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("ollama down")
    monkeypatch.setattr(main.httpx, "get", _boom)
    out = main._check_ollama()
    assert out["status"] == "error" and "detail" in out


def test_check_pgvector_error_is_failopen_dict(monkeypatch):
    monkeypatch.setattr(main.psycopg2, "connect",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no pg")))
    out = main._check_pgvector()
    assert out["status"] == "error" and "no pg" in out["detail"]


def test_check_qdrant_ok_parses_collections(monkeypatch):
    class _CM:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"result": {"collections": [{"name": "weyland_chunks"}]}}).encode()
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: _CM())
    out = main._check_qdrant()
    assert out["status"] == "ok" and out["collections"] == [{"name": "weyland_chunks"}]


# ── endpoints via TestClient ─────────────────────────────────────────────────────────────────────────
def test_health_is_ok_with_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "weyland-tool-server", "version": main.VERSION}


def test_ready_returns_503_when_embed_model_not_loaded(client):
    # embed_model is None (no lifespan) → not ready, and it must not even reach pgvector.
    assert main.embed_model is None
    r = client.get("/ready")
    assert r.status_code == 503 and "embedding model not loaded" in r.json()["detail"]


def test_metrics_serves_prometheus_text(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(main.CONTENT_TYPE_LATEST.split(";")[0])
    assert "# HELP" in r.text or "# TYPE" in r.text


def test_status_reports_degraded_when_backends_unreachable(client, monkeypatch):
    # Stub every backend check to a fail-open error dict — hermetic (no real network) and deterministic.
    for fn in ("_check_pgvector", "_check_qdrant", "_check_weaviate", "_check_neo4j", "_check_ollama"):
        monkeypatch.setattr(main, fn, lambda: {"status": "error", "detail": "unreachable"})
    body = client.get("/status").json()
    assert body["service"] == "weyland-tool-server"
    assert body["status"] == "degraded"
    assert body["model"]["loaded"] is False
    assert set(body["backends"]) == {"pgvector", "qdrant", "weaviate", "neo4j"}


def test_pgvector_health_includes_host(client):
    body = client.get("/pgvector/health").json()
    assert "status" in body and body["pgvector_host"].endswith(str(main.PG_PORT))


def test_context_search_rejects_unknown_backend(client):
    r = client.post("/context/search", params={"backend": "mongo"}, json={"query": "hi"})
    assert r.status_code == 400 and "Unknown backend" in r.json()["detail"]


def test_context_search_403_when_input_guard_blocks(client, monkeypatch):
    from guardrails.verdict import Verdict
    monkeypatch.setattr(main, "_guard",
                        lambda *a, **k: Verdict("pii", Decision.BLOCK, 0.9, "pii detected", 0))
    r = client.post("/context/search", params={"backend": "pgvector"}, json={"query": "ssn?"})
    assert r.status_code == 403 and "pii detected" in r.json()["detail"]


def test_context_search_happy_path_returns_results(client, monkeypatch):
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    fake = [{"source": "d.md", "chunk_index": 1, "similarity": 0.8, "content": "hit"}]
    monkeypatch.setitem(main.SEARCH_FNS, "pgvector", lambda q, limit: fake)
    r = client.post("/context/search", params={"backend": "pgvector"}, json={"query": "what", "limit": 3})
    assert r.status_code == 200
    assert r.json() == {"query": "what", "results": fake}


def test_context_ask_rejects_unknown_backend(client):
    r = client.post("/context/ask", json={"query": "hi", "backend": "mongo"})
    assert r.status_code == 400 and "Unknown backend" in r.json()["detail"]


def test_context_ask_grounds_answer_and_shapes_response(client, monkeypatch):
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    chunks = [{"source": "d.md", "chunk_index": 0, "similarity": 0.9, "content": "the sky is blue"}]
    monkeypatch.setitem(main.SEARCH_FNS, "pgvector", lambda q, limit: chunks)
    monkeypatch.setattr(main, "_ollama_chat", lambda messages, model: "blue, per d.md")
    r = client.post("/context/ask", json={"query": "sky color?", "backend": "pgvector"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "blue, per d.md" and body["sources"] == chunks and body["model"] == main.OLLAMA_MODEL


def test_context_ask_502_when_llm_fails(client, monkeypatch):
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    monkeypatch.setitem(main.SEARCH_FNS, "pgvector", lambda q, limit: [])

    def _boom(messages, model):
        raise httpx.HTTPError("llm down")
    monkeypatch.setattr(main, "_ollama_chat", _boom)
    r = client.post("/context/ask", json={"query": "q", "backend": "pgvector"})
    assert r.status_code == 502 and "LLM call failed" in r.json()["detail"]


def test_list_models_502_when_ollama_down(client, monkeypatch):
    monkeypatch.setattr(main, "_check_ollama", lambda: {"status": "error", "detail": "down"})
    r = client.get("/models")
    assert r.status_code == 502 and "Ollama unreachable" in r.json()["detail"]


def test_list_models_ok(client, monkeypatch):
    monkeypatch.setattr(main, "_check_ollama", lambda: {"status": "ok", "models": ["a", "b"]})
    body = client.get("/models").json()
    assert body == {"default": main.OLLAMA_MODEL, "available": ["a", "b"]}


def test_pipeline_trigger_rejects_unknown_job(client):
    # PipelineTriggerRequest.job_name is a Literal — an unknown job is a 422 validation error.
    r = client.post("/pipeline/trigger", json={"job_name": "rm_rf_prod"})
    assert r.status_code == 422


def test_pipeline_trigger_launches_valid_job(client, monkeypatch):
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    monkeypatch.setattr(main, "_launch_dagster_job",
                        lambda job: {"status": "ok", "run_id": "r1", "job_name": job})
    body = client.post("/pipeline/trigger", json={"job_name": "weyland_ingestion_job"}).json()
    assert body == {"status": "ok", "run_id": "r1", "job_name": "weyland_ingestion_job"}


def test_launch_dagster_job_maps_success(monkeypatch):
    class _R:
        def raise_for_status(self): pass
        def json(self): return {"data": {"launchRun": {"__typename": "LaunchRunSuccess", "run": {"runId": "abc"}}}}
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _R())
    assert main._launch_dagster_job("weyland_eval_job") == {
        "status": "ok", "run_id": "abc", "job_name": "weyland_eval_job"}


def test_launch_dagster_job_502_on_python_error(monkeypatch):
    from fastapi import HTTPException
    class _R:
        def raise_for_status(self): pass
        def json(self): return {"data": {"launchRun": {"__typename": "PythonError", "message": "boom"}}}
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _R())
    with pytest.raises(HTTPException) as exc:
        main._launch_dagster_job("weyland_eval_job")
    assert exc.value.status_code == 502 and "boom" in exc.value.detail


# ── eval endpoints (fake pg connection, assert the shaped rows) ──────────────────────────────────────
class _FakeCursor:
    def __init__(self, fetchone=None, fetchall=None):
        self._one, self._all = fetchone, fetchall or []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, *a, **k): pass
    def fetchone(self): return self._one
    def fetchall(self): return self._all


class _FakeConn:
    def __init__(self, cur): self._cur = cur
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self._cur


def test_evals_leaderboard_404_when_no_scored_run(client, monkeypatch):
    monkeypatch.setattr(main, "_eval_pg_conn", lambda: _FakeConn(_FakeCursor(fetchone=None)))
    r = client.get("/evals/leaderboard")
    assert r.status_code == 404 and "no scored eval run" in r.json()["detail"]


def test_evals_leaderboard_shapes_rows(client, monkeypatch):
    rows = [("gpt-oss:20b", 0.912, 0.874, 0.833, 3)]
    monkeypatch.setattr(main, "_eval_pg_conn", lambda: _FakeConn(_FakeCursor(fetchall=rows)))
    body = client.get("/evals/leaderboard", params={"run_id": 7}).json()
    assert body["run_id"] == 7
    lb = body["leaderboard"][0]
    assert lb["model"] == "gpt-oss:20b" and lb["faithfulness"] == 0.912 and lb["judges"] == 3


def test_evals_runs_shapes_rows(client, monkeypatch):
    import datetime
    rows = [(5, datetime.datetime(2026, 9, 16, 12, 0), "scored", ["m1"], 42, "note")]
    monkeypatch.setattr(main, "_eval_pg_conn", lambda: _FakeConn(_FakeCursor(fetchall=rows)))
    body = client.get("/evals/runs").json()
    run = body["runs"][0]
    assert run["id"] == 5 and run["status"] == "scored" and run["question_count"] == 42
    assert run["created_at"] == "2026-09-16T12:00:00"
