"""Tests for the weyland-guard FastAPI service (app.py) — the HTTP seam around the guardrail pipeline.

Two behaviours matter and are asserted as real responses (not mock calls):
  * FAIL-OPEN: the guards are advisory — if the pipeline isn't loaded, every /guard/* route must return
    decision="allow" (never take an answer offline), /ready must 503, /health must still 200. We drive the app
    WITHOUT its lifespan (TestClient(app), no `with`), so `guardrails` stays None — exactly the pipeline-down state.
  * ADMIN AUTH + mode override: /admin/* is fail-closed (503 when GUARD_ADMIN_TOKEN unset, 401 on a bad bearer),
    and a valid token drives the real in-process mode-override logic (guardrails.config).
"""
import pytest
from fastapi.testclient import TestClient

import app as guard_app
from guardrails.config import clear_overrides


@pytest.fixture
def client():
    # No `with` → lifespan (model loading) does NOT run → guardrails stays None (pipeline-down / fail-open state).
    return TestClient(guard_app.app)


@pytest.fixture(autouse=True)
def _clean_overrides():
    clear_overrides()
    yield
    clear_overrides()


# ── fail-open scoring routes ─────────────────────────────────────────────────────────────────────────
def test_health_is_ok_even_with_pipeline_down(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "validators": []}


def test_ready_is_503_until_models_load(client):
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "loading"


def test_guard_input_fails_open_to_allow(client):
    r = client.post("/guard/input", json={"request_id": "r1", "query": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body == {"request_id": "r1", "decision": "allow", "verdict": None}


def test_guard_output_and_act_fail_open_to_allow(client):
    ro = client.post("/guard/output", json={"request_id": "r2", "answer": "a", "sources": [{"content": "c"}]})
    assert ro.status_code == 200 and ro.json()["decision"] == "allow"
    ra = client.post("/guard/act", json={"request_id": "r3", "tool": "scale", "params": {"n": 1}})
    assert ra.status_code == 200 and ra.json()["decision"] == "allow"


def test_guard_input_validates_request_body(client):
    assert client.post("/guard/input", json={"query": "no request_id"}).status_code == 422


# ── admin auth (fail-closed) ─────────────────────────────────────────────────────────────────────────
def test_admin_disabled_returns_503_when_token_unconfigured(client, monkeypatch):
    monkeypatch.setattr(guard_app, "ADMIN_TOKEN", "")
    r = client.get("/admin/mode")
    assert r.status_code == 503 and "admin disabled" in r.json()["detail"]


def test_admin_rejects_missing_or_wrong_bearer(client, monkeypatch):
    monkeypatch.setattr(guard_app, "ADMIN_TOKEN", "s3cret")
    assert client.get("/admin/mode").status_code == 401                               # no header
    assert client.get("/admin/mode", headers={"Authorization": "Bearer nope"}).status_code == 401


# ── admin mode-override logic (real guardrails.config) ─────────────────────────────────────────────────
def _auth(monkeypatch):
    monkeypatch.setattr(guard_app, "ADMIN_TOKEN", "s3cret")
    return {"Authorization": "Bearer s3cret"}


def test_admin_get_mode_lists_overrides_and_validators(client, monkeypatch):
    h = _auth(monkeypatch)
    body = client.get("/admin/mode", headers=h).json()
    assert body["overrides"] == {} and isinstance(body["validators"], list) and body["validators"]


def test_admin_set_mode_applies_override_to_named_validator(client, monkeypatch):
    h = _auth(monkeypatch)
    r = client.post("/admin/mode", headers=h, json={"mode": "block", "validators": ["policy.gate"]})
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] == {"mode": "block", "validators": ["policy.gate"]}
    assert "policy.gate" in body["overrides"]                 # override recorded (value format is config's own)


def test_admin_set_mode_rejects_bad_mode(client, monkeypatch):
    h = _auth(monkeypatch)
    r = client.post("/admin/mode", headers=h, json={"mode": "banana"})
    assert r.status_code == 400 and "bad mode" in r.json()["error"]


def test_admin_reset_clears_overrides(client, monkeypatch):
    h = _auth(monkeypatch)
    client.post("/admin/mode", headers=h, json={"mode": "flag", "validators": ["policy.gate"]})
    r = client.post("/admin/mode/reset", headers=h)
    assert r.status_code == 200 and r.json()["overrides"] == {}
