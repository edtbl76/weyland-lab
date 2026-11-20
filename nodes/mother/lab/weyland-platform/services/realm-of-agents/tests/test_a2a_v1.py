"""A2A behind Bifrost's Agent Gateway (B249, 2026-11-19): the v1 binding, the spend lane, and the conversation id.

Bifrost's gateway speaks only A2A v1 (`SendMessage`, parts `{"text": …}`, roles `ROLE_USER`/`ROLE_AGENT`, a result
wrapped as `{"message": {...}}` — shapes read from a2a-go v2.5.0, the gateway's client). The Realm keeps 0.3
(`message/send`) for direct callers such as the a2a-inspector.

The spend rule (B209: the Realm spends nothing unless the caller is entitled): BOTH A2A methods run free-only, except a
v1 call that asks for paid (`metadata.allow_paid`) AND carries the gateway token Bifrost sends on every call it forwards
(`X-Realm-Gateway-Token`, registration `runtime_auth`). Bifrost grants the Realm only to the operator's key, so the
token means "the operator, through the gateway". A direct caller, or an unset token, is never paid.

The A2A context id is the dispatch's session id, so Bifrost's Agent Logs and Langfuse key the conversation alike.
a2a.py is loaded from its file under its own name: test_app.py replaces `a2a` in sys.modules with a stub.
"""
import importlib.util
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import budget
import roster

_SRC = pathlib.Path(__file__).resolve().parent.parent / "a2a.py"


def _load(monkeypatch, token="gw-secret"):
    if token is None:
        monkeypatch.delenv("REALM_GATEWAY_TOKEN", raising=False)
    else:
        monkeypatch.setenv("REALM_GATEWAY_TOKEN", token)
    spec = importlib.util.spec_from_file_location("realm_a2a_under_test", _SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []

    async def dispatch(task, history=None, session_id=None):
        calls.append({"kind": "dispatch", "task": task, "free_only": budget.is_free_only(), "session_id": session_id})
        return "odin", f"answer to {task}"

    async def run_agent(spec, task, history=None, session_id=None):
        calls.append({"kind": "agent", "key": spec.key, "task": task, "free_only": budget.is_free_only(),
                      "session_id": session_id})
        return f"{spec.key} says hi"

    monkeypatch.setattr(mod.gna, "dispatch", dispatch)
    monkeypatch.setattr(mod.gna, "run_agent", run_agent)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app), calls


def _v1(text, metadata=None, context_id=None):
    msg = {"messageId": "m-1", "role": "ROLE_USER", "parts": [{"text": text}]}
    if metadata is not None:
        msg["metadata"] = metadata
    if context_id:
        msg["contextId"] = context_id
    return {"jsonrpc": "2.0", "id": "r-1", "method": "SendMessage", "params": {"message": msg}}


def _v03(text, metadata=None):
    msg = {"role": "user", "kind": "message", "messageId": "m-0", "parts": [{"kind": "text", "text": text}]}
    if metadata is not None:
        msg["metadata"] = metadata
    return {"jsonrpc": "2.0", "id": "r-0", "method": "message/send", "params": {"message": msg}}


GW = {"X-Realm-Gateway-Token": "gw-secret"}


def test_v1_send_message_answers_in_the_v1_shape_with_who_answered(monkeypatch):
    client, calls = _load(monkeypatch)
    r = client.post("/a2a", json=_v1("which realm handles data quality?", context_id="ctx-7")).json()
    msg = r["result"]["message"]
    assert r["id"] == "r-1" and msg["role"] == "ROLE_AGENT"
    assert msg["parts"] == [{"text": "answer to which realm handles data quality?"}]
    assert msg["contextId"] == "ctx-7" and msg["messageId"]
    assert msg["metadata"]["routed_to"] == "odin" and msg["metadata"]["god"] == roster.BY_KEY["odin"].god
    assert calls[0]["task"] == "which realm handles data quality?"


def test_v1_uses_the_context_id_as_the_session_and_makes_one_when_absent(monkeypatch):
    client, calls = _load(monkeypatch)
    client.post("/a2a", json=_v1("q", context_id="ctx-7"))
    assert calls[-1]["session_id"] == "ctx-7"
    r = client.post("/a2a", json=_v1("q")).json()
    made = r["result"]["message"]["contextId"]
    assert made and calls[-1]["session_id"] == made


def test_v1_per_agent_endpoint_runs_that_agent(monkeypatch):
    client, calls = _load(monkeypatch)
    r = client.post("/a2a/odin", json=_v1("hi")).json()
    assert r["result"]["message"]["parts"] == [{"text": "odin says hi"}]
    assert calls[-1]["kind"] == "agent" and calls[-1]["key"] == "odin"


def test_paid_only_with_allow_paid_and_the_gateway_token(monkeypatch):
    client, calls = _load(monkeypatch)
    client.post("/a2a", json=_v1("q", {"allow_paid": True}), headers=GW)
    assert calls[-1]["free_only"] is False


@pytest.mark.parametrize("metadata,headers", [
    ({"allow_paid": True}, {}),                                          # no token: a direct caller
    ({"allow_paid": True}, {"X-Realm-Gateway-Token": "wrong"}),          # wrong token
    ({}, GW),                                                            # token but no request for paid
    ({"allow_paid": "yes"}, GW),                                         # only a real true counts
])
def test_v1_is_free_otherwise(monkeypatch, metadata, headers):
    client, calls = _load(monkeypatch)
    client.post("/a2a", json=_v1("q", metadata), headers=headers)
    assert calls[-1]["free_only"] is True


def test_an_unset_gateway_token_is_never_paid(monkeypatch):
    client, calls = _load(monkeypatch, token=None)
    client.post("/a2a", json=_v1("q", {"allow_paid": True}), headers={"X-Realm-Gateway-Token": ""})
    assert calls[-1]["free_only"] is True


def test_v03_message_send_still_works_and_is_always_free(monkeypatch):
    # Was paid by default until 2026-11-19 (the A2A handler never entered free_only): a gap against B209.
    client, calls = _load(monkeypatch)
    r = client.post("/a2a", json=_v03("hello", {"allow_paid": True}), headers=GW).json()
    assert r["result"]["kind"] == "message" and r["result"]["parts"][0]["text"] == "answer to hello"
    assert calls[-1]["free_only"] is True


def test_v1_without_text_is_invalid_params(monkeypatch):
    client, _ = _load(monkeypatch)
    body = _v1("x")
    body["params"]["message"]["parts"] = [{"data": {"a": 1}}]
    assert client.post("/a2a", json=body).json()["error"]["code"] == -32602


def test_unknown_method_is_method_not_found(monkeypatch):
    client, _ = _load(monkeypatch)
    body = _v1("x")
    body["method"] = "GetTask"
    assert client.post("/a2a", json=body).json()["error"]["code"] == -32601
