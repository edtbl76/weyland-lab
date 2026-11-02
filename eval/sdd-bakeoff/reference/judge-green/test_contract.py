"""Black-box judge for the store-scaler trial: the task's interface, over HTTP, with the kubernetes module stubbed.
Run from the trial's service dir: SERVICE_DIR=<dir> python -m pytest -q <this file>. Asserts only what the task text
states (routes, status codes, response shape, the phrases it names, the scale call); never private function names."""
import importlib
import os
import sys
import types

import pytest

CALLS = []
# STATEFUL and with a read method, like a real Deployment (fixed 2026-10-31): an implementation that reads the scale
# back (to verify a wake, or for a status endpoint) must see what it wrote, not an AttributeError.
STATE = {}


class _Scale:
    def __init__(self, replicas):
        self.spec = types.SimpleNamespace(replicas=replicas)
        self.status = types.SimpleNamespace(replicas=replicas)


class _FakeApps:
    def patch_namespaced_deployment_scale(self, name=None, namespace=None, body=None, **kw):
        CALLS.append({"name": name, "namespace": namespace, "body": body})
        STATE[name] = (body or {}).get("spec", {}).get("replicas")
        return _Scale(STATE[name])

    def read_namespaced_deployment_scale(self, name=None, namespace=None, **kw):
        return _Scale(STATE.get(name, 0))

    # The real AppsV1Api also has the StatefulSet scale methods (cassandra is a StatefulSet in this repo).
    patch_namespaced_stateful_set_scale = patch_namespaced_deployment_scale
    read_namespaced_stateful_set_scale = read_namespaced_deployment_scale


def _stub_kubernetes():
    k8s = types.ModuleType("kubernetes")
    client = types.ModuleType("kubernetes.client")
    client.AppsV1Api = _FakeApps
    config = types.ModuleType("kubernetes.config")
    config.load_incluster_config = lambda *a, **k: None
    config.load_kube_config = lambda *a, **k: None
    k8s.client, k8s.config = client, config
    sys.modules.update({"kubernetes": k8s, "kubernetes.client": client, "kubernetes.config": config})


@pytest.fixture(scope="module")
def svc():
    _stub_kubernetes()
    sys.path.insert(0, os.environ["SERVICE_DIR"])
    sys.modules.pop("app", None)
    mod = importlib.import_module("app")
    from fastapi.testclient import TestClient
    return mod, TestClient(mod.app)


def post(svc, body):
    CALLS.clear()
    return svc[1].post("/scale", json=body)


def test_healthz(svc):
    r = svc[1].get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_namespace_default(svc):
    assert svc[0].NAMESPACE == "data-mesh"


def test_wake_scales_to_1(svc):
    r = post(svc, {"store": "mysql", "action": "wake"})
    assert r.status_code == 200
    assert r.json() == {"store": "mysql", "namespace": "data-mesh", "replicas": 1, "status": "woke"}
    assert CALLS == [{"name": "mysql", "namespace": "data-mesh", "body": {"spec": {"replicas": 1}}}]


def test_sleep_scales_to_0(svc):
    r = post(svc, {"store": "mongodb", "action": "sleep"})
    assert r.status_code == 200 and r.json()["replicas"] == 0 and r.json()["status"] == "slept"
    assert CALLS[-1]["body"] == {"spec": {"replicas": 0}} and CALLS[-1]["name"] == "mongodb"


def test_explicit_replicas(svc):
    r = post(svc, {"store": "cockroachdb", "replicas": 1})
    assert r.status_code == 200 and r.json()["status"] == "woke" and CALLS[-1]["body"] == {"spec": {"replicas": 1}}


def test_nested_port_payload(svc):
    r = post(svc, {"run": {"id": "r1", "properties": {"deep": {"store": "gizmosql", "action": "wake"}}}})
    assert r.status_code == 200 and r.json()["store"] == "gizmosql" and CALLS[-1]["name"] == "gizmosql"


@pytest.mark.parametrize("body,phrase", [
    ({"store": "postgres", "action": "wake"}, "allowlist"),
    ({"store": "mysql", "action": "restart"}, "must be one of"),
    ({"store": "mysql", "replicas": 3}, "0 (sleep) or 1 (wake)"),
    ({"store": "mysql"}, "need replicas"),
])
def test_rejections_make_no_scale_call(svc, body, phrase):
    r = post(svc, body)
    assert r.status_code == 400, r.text
    assert phrase in str(r.json().get("detail")), r.json()
    assert CALLS == []
