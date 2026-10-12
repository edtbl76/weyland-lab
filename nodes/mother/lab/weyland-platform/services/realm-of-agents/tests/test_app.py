"""Tests for the Realm of Agents FastAPI surface (app.py) — the discovery + tasking + ops endpoints.

Driven with TestClient (no `with`, so the MLflow-autolog lifespan is skipped and /ready reports loading). The
discovery/ops endpoints run against the REAL cards/roster/config; the two tasking endpoints stub the router
(gna.dispatch / gna.run_agent) and assert the real response shaping + the fail paths (unknown agent → 404,
dispatch error → 502). a2a + mlflow are stubbed — app.py imports them at module scope but neither is exercised here.
"""
import sys
import types

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

# app.py does `import mlflow`, `import a2a`, and `app.include_router(a2a.router)` at module scope.
sys.modules.setdefault("mlflow", types.ModuleType("mlflow"))
_a2a = types.ModuleType("a2a"); _a2a.router = APIRouter(); sys.modules["a2a"] = _a2a

import app as realm_app  # noqa: E402 — conftest already put the service dir on sys.path


@pytest.fixture
def client():
    return TestClient(realm_app.app)   # no `with` → lifespan skipped → _ready stays False


def test_health_reports_service_and_agent_count(client):
    b = client.get("/health").json()
    assert b["status"] == "ok" and b["service"] == "realm-of-agents" and b["agents"] == len(realm_app.ROSTER)


def test_ready_is_503_before_lifespan_runs(client):
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["status"] == "loading"


def test_metrics_serves_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200 and b"realm_requests_total" in r.content


def test_console_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200 and "Realm of Agents" in r.text


def test_root_card_is_the_service_card(client):
    b = client.get("/.well-known/agent-card.json").json()
    assert b["name"] == "Realm of Agents" and len(b["skills"]) == len(realm_app.ROSTER)


def test_list_agents_indexes_realms_and_cards(client):
    b = client.get("/agents").json()
    assert set(b["realms"]) == set(realm_app.REALMS)
    assert len(b["agents"]) == len(realm_app.ROSTER)
    assert set(b["realms"]["Root"]) == {"operator", "gna"}


def test_prompts_returns_baked_prompt_per_agent(client):
    b = client.get("/prompts").json()
    assert "odin" in b and b["odin"]["god"] == "Odin" and b["odin"]["prompt"]


def test_agent_card_ok_and_unknown_404(client):
    assert client.get("/agents/odin/card").json()["key"] == "odin"
    assert client.get("/agents/nope/card").status_code == 404


def test_route_dispatches_and_reports_the_agent(client, monkeypatch):
    async def fake_dispatch(msg, hist=None):
        return ("odin", "the answer")
    monkeypatch.setattr(realm_app.gna, "dispatch", fake_dispatch)
    b = client.post("/route", json={"message": "build X"}).json()
    assert b["routed_to"] == "odin" and b["answer"] == "the answer"
    assert b["god"] == realm_app.BY_KEY["odin"].god


def test_route_dispatch_failure_is_502(client, monkeypatch):
    async def boom(msg, hist=None):
        raise RuntimeError("classifier down")
    monkeypatch.setattr(realm_app.gna, "dispatch", boom)
    assert client.post("/route", json={"message": "x"}).status_code == 502


def test_route_is_paid_by_default_and_free_only_on_request(client, monkeypatch):
    # 2026-10-12: an automatic caller (the ship-images Realm transaction) sends allow_paid false and the whole
    # dispatch runs in budget.free_only(); a person's request keeps the hosted brain.
    import budget
    seen = []

    async def fake_dispatch(msg, hist=None):
        seen.append(budget.is_free_only())
        return ("huginn", "it subtracts")
    monkeypatch.setattr(realm_app.gna, "dispatch", fake_dispatch)
    assert client.post("/route", json={"message": "x"}).status_code == 200
    assert client.post("/route", json={"message": "x", "allow_paid": False}).status_code == 200
    assert seen == [False, True]
    assert not budget.is_free_only()   # the mode never outlives its request


def test_route_documents_its_502():
    assert "502" in realm_app.app.openapi()["paths"]["/route"]["post"]["responses"]


def test_the_committed_contract_snapshot_matches_the_app():
    # docs/api/specs/realm-of-agents.openapi.json is the locked contract the api-drift cron compares the LIVE service to.
    import json
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[7]
    sys.path.insert(0, str(root / "scripts" / "lib"))
    import api_spec_diff
    snapshot = json.loads((root / "docs" / "api" / "specs" / "realm-of-agents.openapi.json").read_text())
    # The A2A router is stubbed above (a2a.py needs the a2a SDK), so its /a2a/* routes are out of this comparison.
    snapshot["paths"] = {p: v for p, v in snapshot["paths"].items() if not p.startswith("/a2a")}
    assert api_spec_diff.diff(snapshot, realm_app.app.openapi()) == []
    assert api_spec_diff.diff(realm_app.app.openapi(), snapshot) == []


def test_send_message_runs_agent_and_unknown_404(client, monkeypatch):
    async def fake_run(spec, msg, hist):
        return "done"
    monkeypatch.setattr(realm_app.gna, "run_agent", fake_run)
    b = client.post("/agents/odin/message", json={"message": "hi"}).json()
    assert b["agent"] == "odin" and b["answer"] == "done" and b["realm"] == realm_app.BY_KEY["odin"].realm
    assert client.post("/agents/nope/message", json={"message": "hi"}).status_code == 404
