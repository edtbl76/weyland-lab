"""Tests for store-scaler — the in-cluster wake/sleep executor behind the Port button.

Two risks, both silent if wrong: the recursive input-finder (`_find_inputs`/`_extract`) must locate {store,action}
wherever the Port polling payload nests them, and the /scale allowlist + wake→1/sleep→0 translation must reject
anything off-allowlist or off-{0,1} BEFORE it patches a deployment's replicas. Tests assert real responses + the
exact scale call recorded by the fake k8s client — never "a mock was called".
"""
import app as scaler
from fastapi.testclient import TestClient

client = TestClient(scaler.app)


# ── pure input extraction ────────────────────────────────────────────────────────────────────────
def test_find_inputs_locates_the_store_action_dict_when_nested():
    payload = {"run": {"foo": 1, "properties": {"deep": {"store": "mysql", "action": "wake"}}}}
    assert scaler._find_inputs(payload) == {"store": "mysql", "action": "wake"}


def test_find_inputs_returns_none_when_absent():
    assert scaler._find_inputs({"a": {"b": [1, 2, {"action": "wake"}]}}) is None  # needs BOTH store+action


def test_extract_simple_body():
    assert scaler._extract({"store": "mysql", "replicas": 1, "action": None}) == ("mysql", 1, None)


def test_extract_from_nested_port_payload():
    assert scaler._extract({"x": {"store": "mongodb", "action": "sleep"}}) == ("mongodb", None, "sleep")


# ── /scale behavior via TestClient ──────────────────────────────────────────────────────────────────
def test_healthz():
    assert client.get("/healthz").json() == {"ok": True}


def test_scale_wake_sets_replicas_1_and_patches(monkeypatch):
    scaler._apps.calls.clear()
    r = client.post("/scale", json={"store": "mysql", "action": "wake"})
    assert r.status_code == 200
    assert r.json() == {"store": "mysql", "namespace": scaler.NAMESPACE, "replicas": 1, "status": "woke"}
    assert scaler._apps.calls[-1] == {"name": "mysql", "namespace": scaler.NAMESPACE,
                                      "body": {"spec": {"replicas": 1}}}


def test_scale_sleep_sets_replicas_0():
    scaler._apps.calls.clear()
    r = client.post("/scale", json={"store": "mysql", "action": "sleep"})
    assert r.status_code == 200 and r.json()["replicas"] == 0 and r.json()["status"] == "slept"
    assert scaler._apps.calls[-1]["body"] == {"spec": {"replicas": 0}}


def test_scale_rejects_store_off_allowlist():
    r = client.post("/scale", json={"store": "postgres", "action": "wake"})
    assert r.status_code == 400 and "allowlist" in r.json()["detail"]


def test_scale_rejects_unknown_action():
    r = client.post("/scale", json={"store": "mysql", "action": "restart"})
    assert r.status_code == 400 and "must be one of" in r.json()["detail"]


def test_scale_rejects_replicas_other_than_0_or_1():
    r = client.post("/scale", json={"store": "mysql", "replicas": 3})
    assert r.status_code == 400 and "0 (sleep) or 1 (wake)" in r.json()["detail"]


def test_scale_rejects_missing_replicas_and_action():
    r = client.post("/scale", json={"store": "mysql"})
    assert r.status_code == 400 and "need replicas" in r.json()["detail"]
