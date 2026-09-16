"""Tests for the operator's read tools (B66 Part 1) — thin HTTP wrappers over the tool-server's read plane.

Contract: each tool returns the tool-server's response TEXT on success and an error STRING (never raises) on
failure, so the agent can react instead of crashing; and `propose_act` only ever PROPOSES (it must never claim to
have run anything). httpx is stubbed — we assert the returned strings, not that a client was called.
"""
import httpx

import tools


def test_status_returns_toolserver_text(monkeypatch):
    monkeypatch.setattr(tools.httpx, "get", lambda url, timeout=None: type("R", (), {"text": '{"status":"ok"}'})())
    assert tools.status.func() == '{"status":"ok"}' if hasattr(tools.status, "func") else tools.status() == '{"status":"ok"}'


def test_status_returns_error_string_on_failure(monkeypatch):
    def _boom(*a, **k): raise httpx.ConnectError("down")
    monkeypatch.setattr(tools.httpx, "get", _boom)
    out = tools.status() if not hasattr(tools.status, "func") else tools.status.func()
    assert "error" in out and "status failed" in out


def test_context_search_posts_and_returns_text(monkeypatch):
    captured = {}
    def _post(url, params=None, json=None, timeout=None):
        captured["params"] = params; captured["json"] = json
        return type("R", (), {"text": "chunks"})()
    monkeypatch.setattr(tools.httpx, "post", _post)
    fn = tools.context_search.func if hasattr(tools.context_search, "func") else tools.context_search
    assert fn("what is X", backend="qdrant") == "chunks"
    assert captured["params"] == {"backend": "qdrant"}
    assert captured["json"]["query"] == "what is X"


def test_context_ask_returns_error_string_on_failure(monkeypatch):
    def _boom(*a, **k): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(tools.httpx, "post", _boom)
    fn = tools.context_ask.func if hasattr(tools.context_ask, "func") else tools.context_ask
    out = fn("q")
    assert "error" in out and "context_ask failed" in out


def test_propose_act_only_proposes_never_claims_execution():
    fn = tools.propose_act.func if hasattr(tools.propose_act, "func") else tools.propose_act
    out = fn(tool="pipeline_trigger", summary="run it", job_name="weyland_eval_job")
    assert "Proposed" in out and "confirm" in out
    assert "Launched" not in out and "✅" not in out       # proposing must never read as "it ran"
