"""POST /operator/ask — the free-only flag (2026-10-10).

A person chatting may fail over to paid Haiku, so the operator still answers them. An AUTOMATIC caller (the ship-images
TXN check) must spend nothing: it sends `"allow_paid": false`, which runs agent.run(..., allow_fallback=False), the same
unpaid path the incident sweep uses. When the free local brain is down, that is a 503 the caller can read — never a
silent answer from Haiku. `agent` is the conftest stub; mlflow is stubbed here because app.py imports it at module scope.
"""
import sys
import types

import pytest

sys.modules.setdefault("mlflow", types.SimpleNamespace(set_tracking_uri=lambda *_: None,
                                                       set_experiment=lambda *_: None))

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402  (the conftest stub)
import app as app_mod  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    calls = []

    async def fake_run(message, history=None, session_id=None, user_id=None, allow_fallback=True, trace=None):
        calls.append(allow_fallback)
        return ("There are 42 namespaces.", None)

    monkeypatch.setattr(agent, "run", fake_run)
    monkeypatch.setattr(app_mod, "guard", lambda *a, **k: False)
    return TestClient(app_mod.app), calls


def test_ask_is_free_by_default_and_paid_only_on_request(client):
    # B211 (2026-10-14): free by default, like the Realm (B209), so a caller who never asked cannot spend on the Haiku
    # fallback. Its callers (14 days) were the ship-images transaction (sends false), Prometheus and api-drift.
    c, calls = client
    r = c.post("/operator/ask", json={"message": "how many namespaces?"})
    assert r.status_code == 200 and r.json()["reply"] == "There are 42 namespaces."
    r = c.post("/operator/ask", json={"message": "how many namespaces?", "allow_paid": True})
    assert r.status_code == 200
    assert calls == [False, True]


def test_allow_paid_false_runs_on_the_unpaid_path(client):
    c, calls = client
    r = c.post("/operator/ask", json={"message": "how many namespaces?", "allow_paid": False})
    assert r.status_code == 200
    assert calls == [False]


def test_free_only_with_the_local_brain_down_is_a_503_that_says_so(client, monkeypatch):
    c, _ = client

    async def down(*_a, **_k):
        raise agent.LocalUnavailable("local brain qwen failed its health pre-check")

    monkeypatch.setattr(agent, "run", down)
    r = c.post("/operator/ask", json={"message": "how many namespaces?", "allow_paid": False})
    assert r.status_code == 503
    assert "local brain unavailable" in r.json()["detail"]


def test_the_error_responses_are_documented_in_the_contract():
    # Sonar python:S8415 failed CI #318 on the undocumented 503; every status the endpoint raises is in its OpenAPI.
    responses = app_mod.app.openapi()["paths"]["/operator/ask"]["post"]["responses"]
    assert {"403", "502", "503"} <= set(responses)


def test_the_committed_contract_snapshot_matches_the_app():
    # docs/api/specs/weyland-operator.openapi.json is the locked contract the api-drift cron compares the LIVE service
    # to. Hold it to what this code generates, so a hand-edited snapshot cannot drift from the app it describes.
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[7]
    sys.path.insert(0, str(root / "scripts" / "lib"))
    import api_spec_diff
    snapshot = json.loads((root / "docs" / "api" / "specs" / "weyland-operator.openapi.json").read_text())
    assert api_spec_diff.diff(snapshot, app_mod.app.openapi()) == []
    assert api_spec_diff.diff(app_mod.app.openapi(), snapshot) == []


def test_any_other_run_failure_is_still_a_502(client, monkeypatch):
    c, _ = client

    async def broken(*_a, **_k):
        raise RuntimeError("graph exploded")

    monkeypatch.setattr(agent, "run", broken)
    r = c.post("/operator/ask", json={"message": "hi"})
    assert r.status_code == 502 and "graph exploded" in r.json()["detail"]
