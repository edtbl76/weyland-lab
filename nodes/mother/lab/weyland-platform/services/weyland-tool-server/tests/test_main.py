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
from prometheus_client import REGISTRY

import main
from grkit.verdict import Decision, Hook


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


# B207 (2026-10-13): the ACT hook decides AUTHORITY, not content, so it fails CLOSED — a guard that is down must not
# mean "anyone may act". Before this, _guard failed open on every hook and the act endpoints ignored its answer.
@pytest.mark.parametrize("exc, cause", [
    (httpx.ConnectError("guard down"), "connection"),
    (httpx.ReadTimeout("slow"), "timeout"),
])
def test_guard_act_fails_closed_on_transport_error(monkeypatch, exc, cause):
    def _boom(*a, **k):
        raise exc
    monkeypatch.setattr(main.httpx, "post", _boom)
    v = main._guard(Hook.ACT, "req-4", {"tool": "pipeline/trigger"}, "weyland-operator")
    assert v is not None and v.decision == Decision.BLOCK and v.validator == "guard-unavailable"
    assert v.reason == f"guard unavailable ({cause}): action refused"


def test_guard_act_fails_closed_on_an_unreadable_answer(monkeypatch):
    class _Bad:
        def json(self):
            raise ValueError("not json")
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _Bad())
    v = main._guard(Hook.ACT, "req-5", {"tool": "evals/run"})
    assert v is not None and v.decision == Decision.BLOCK and "bad_response" in v.reason


def test_guard_act_with_an_unexpected_decision_fails_closed(monkeypatch):
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _Resp({"decision": "maybe"}))
    assert main._guard(Hook.ACT, "req-6", {"tool": "evals/run"}).decision == Decision.BLOCK
    assert main._guard(Hook.INPUT, "req-7", {"query": "q"}) is None      # content hooks stay fail-open


def test_guard_input_still_fails_open_on_transport_error(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("guard down")
    monkeypatch.setattr(main.httpx, "post", _boom)
    assert main._guard(Hook.INPUT, "req-8", {"query": "q"}) is None


# B207 DoD (2026-10-14): every guard failure is COUNTED by hook and cause. Failing open on content and closed on authority
# is only safe when it is loud: a guard that silently stopped answering means unguarded answers (input/output) or every
# act refused (act), and a mesh denial (403 "RBAC: access denied", not JSON) reads as bad_response. The GuardCallsFailing
# alert reads this counter.
def _failures(hook, cause):
    return REGISTRY.get_sample_value("tool_server_guard_failures_total", {"hook": hook, "cause": cause}) or 0.0


@pytest.mark.parametrize("hook, exc, cause", [
    (Hook.INPUT, httpx.ConnectError("guard down"), "connection"),
    (Hook.OUTPUT, httpx.ReadTimeout("slow"), "timeout"),
    (Hook.ACT, httpx.ConnectError("guard down"), "connection"),
])
def test_every_guard_failure_is_counted_by_hook_and_cause(monkeypatch, hook, exc, cause):
    def _boom(*a, **k):
        raise exc
    monkeypatch.setattr(main.httpx, "post", _boom)
    before = _failures(hook.value, cause)
    main._guard(hook, "req-9", {"query": "q"})
    assert _failures(hook.value, cause) == before + 1


def test_a_mesh_denial_is_counted_as_a_bad_response(monkeypatch):
    class _RbacDenied:   # Istio's 403 body is plain text, so .json() raises
        def json(self):
            raise ValueError("RBAC: access denied")
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _RbacDenied())
    before = _failures("act", "bad_response")
    assert main._guard(Hook.ACT, "req-10", {"tool": "evals/run"}).decision == Decision.BLOCK
    assert _failures("act", "bad_response") == before + 1


@pytest.mark.parametrize("hook", ["input", "output", "act"])
@pytest.mark.parametrize("cause", ["timeout", "connection", "bad_response"])
def test_every_hook_and_cause_series_exists_before_any_failure(hook, cause):
    # The GuardCallsFailing alert is `increase(...[10m]) > 0`. A labelled series that does not exist until the first
    # failure appears already AT 1, and increase() over a series with no earlier sample is 0, so that first failure
    # never alerts (found by the 2026-10-21 DoD re-audit: live /metrics had no series at all). Every combination
    # must therefore be exported from start-up.
    assert REGISTRY.get_sample_value("tool_server_guard_failures_total", {"hook": hook, "cause": cause}) is not None


def test_an_answered_guard_counts_no_failure(monkeypatch):
    monkeypatch.setattr(main.httpx, "post", lambda *a, **k: _Resp({"decision": "allow"}))
    before = _failures("input", "connection") + _failures("input", "timeout") + _failures("input", "bad_response")
    main._guard(Hook.INPUT, "req-11", {"query": "q"})
    after = _failures("input", "connection") + _failures("input", "timeout") + _failures("input", "bad_response")
    assert after == before


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
    from grkit.verdict import Verdict
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


_ACT_BLOCK = main.Verdict("policy.gate", Decision.BLOCK, None, "actor 'rando' is not allowed to act", 0)


@pytest.mark.parametrize("path, body", [
    ("/pipeline/trigger", {"job_name": "weyland_ingestion_job"}),
    ("/evals/run", None),
    ("/evals/score", None),
])
def test_an_act_the_guard_blocks_is_403_and_never_launches(client, monkeypatch, path, body):
    # B207 (2026-10-13): these endpoints used to call the act guard and DISCARD its answer — policy.gate recorded
    # 223 blocks while every act still launched.
    launched = []
    monkeypatch.setattr(main, "_guard", lambda hook, *a, **k: _ACT_BLOCK if hook == Hook.ACT else None)
    monkeypatch.setattr(main, "_launch_dagster_job", lambda job: launched.append(job) or {"status": "ok"})
    r = client.post(path, json=body) if body is not None else client.post(path)
    assert r.status_code == 403
    assert r.json()["detail"] == "blocked by policy.gate: actor 'rando' is not allowed to act"
    assert launched == []


@pytest.mark.parametrize("raw", ["/pipeline%2Ftrigger", "/pipeline%2ftrigger", "/evals%2Frun", "/mcp-act%2Fx",
                                 "/pipeline%5Ctrigger"])
def test_an_encoded_slash_in_the_path_is_refused_before_routing(client, monkeypatch, raw):
    # B207 (2026-10-13), OBSERVED LIVE: Istio's act-path DENY matches exact paths and the mesh does not decode %2F,
    # while uvicorn does — so GET /pipeline%2Ftrigger from a non-gateway pod reached the tool-server (405), not
    # Istio's 403. A POST with a forged `X-Forwarded-Consumer: weyland-operator` would have launched a job.
    launched = []
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    monkeypatch.setattr(main, "_launch_dagster_job", lambda job: launched.append(job) or {"status": "ok"})
    r = client.post(raw, json={"job_name": "weyland_ingestion_job"},
                    headers={"X-Forwarded-Consumer": "weyland-operator"})
    assert r.status_code == 400 and r.json()["detail"] == "encoded path separators are not accepted"
    assert launched == []


def test_ordinary_paths_still_route(client):
    assert client.get("/health").status_code == 200


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


# ── B197 follow-up: eval traffic must not feed the Langfuse online evaluators ─────────────────────────────────────
# Every `rag-generate` observation triggers up to 9 online evaluation rules, each an LLM-as-judge call to gpt-oss:20b on
# rogueone. The offline eval (weyland_eval_job) asks 120 questions through /context/ask, so its own traffic made the
# judge evict the model under test twice per question (found 2026-09-29: 8 alternating model loads in 40 min). The
# eval records its answers in eval_results + MLflow already; it opts out of Langfuse with `langfuse: false`.
class _FakeLangfuse:
    def __init__(self):
        self.observations = []

    def get_prompt(self, *a, **k):
        return None

    def start_as_current_observation(self, **kw):
        self.observations.append(kw.get("name"))
        from contextlib import nullcontext
        return nullcontext(type("G", (), {"update": lambda self, **k: None})())

    def flush(self):
        pass


def _stub_ask(monkeypatch):
    lf = _FakeLangfuse()
    monkeypatch.setattr(main, "_lf", lf)
    monkeypatch.setattr(main, "SEARCH_FNS", {"pgvector": lambda q, n: [{"content": "c", "source": "s", "chunk_index": 0}]})
    monkeypatch.setattr(main, "_ollama_chat", lambda messages, model: "an answer")
    monkeypatch.setattr(main, "_guard", lambda *a, **k: None)
    return lf


def test_context_ask_traces_to_langfuse_by_default(client, monkeypatch):
    lf = _stub_ask(monkeypatch)
    r = client.post("/context/ask", json={"query": "q", "backend": "pgvector"})
    assert r.status_code == 200
    assert lf.observations == ["rag-generate"]


def test_context_ask_with_langfuse_false_creates_no_observation(client, monkeypatch):
    lf = _stub_ask(monkeypatch)
    r = client.post("/context/ask", json={"query": "q", "backend": "pgvector", "langfuse": False})
    assert r.status_code == 200
    assert r.json()["answer"] == "an answer"   # the answer is unaffected — only the Langfuse trace is skipped
    assert lf.observations == []
