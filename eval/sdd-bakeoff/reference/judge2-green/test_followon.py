"""Follow-on judge for store-scaler: GET /status/{store} + cassandra on the default allowlist. Black-box over HTTP with
the kubernetes module stubbed; the fake records every write and answers reads with a fixed replica count.
Run from anywhere: SERVICE_DIR=<dir> python -m pytest -q <this file>   (the round-1 test_contract.py runs separately)."""
import importlib
import os
import sys
import types

import pytest

WRITES, READS = [], []
# STATEFUL like a real Deployment (judge bug fixed 2026-10-31): a write sets the replicas a later read returns. The
# first version answered reads from a fixed table, so an app that verified its own wake by reading back got 0 and 502'd.
STATE = {"mysql": 1}


class _Scale:
    def __init__(self, replicas):
        self.spec = types.SimpleNamespace(replicas=replicas)
        self.status = types.SimpleNamespace(replicas=replicas)


class _FakeApps:
    def patch_namespaced_deployment_scale(self, name=None, namespace=None, body=None, **kw):
        WRITES.append({"name": name, "namespace": namespace, "body": body})
        STATE[name] = (body or {}).get("spec", {}).get("replicas")
        return _Scale(STATE[name])

    def read_namespaced_deployment_scale(self, name=None, namespace=None, **kw):
        READS.append({"name": name, "namespace": namespace})
        return _Scale(STATE.get(name, 0))

    # The real AppsV1Api also scales StatefulSets, and in this repo cassandra IS one (k8s/data-mesh/cassandra.yaml).
    # Trials that read the manifests route it there (judge fix 2026-10-31: the fake first lacked these methods).
    patch_namespaced_stateful_set_scale = patch_namespaced_deployment_scale
    read_namespaced_stateful_set_scale = read_namespaced_deployment_scale


@pytest.fixture(scope="module")
def client():
    k8s = types.ModuleType("kubernetes")
    c = types.ModuleType("kubernetes.client")
    c.AppsV1Api = _FakeApps
    cfg = types.ModuleType("kubernetes.config")
    cfg.load_incluster_config = lambda *a, **k: None
    cfg.load_kube_config = lambda *a, **k: None
    k8s.client, k8s.config = c, cfg
    sys.modules.update({"kubernetes": k8s, "kubernetes.client": c, "kubernetes.config": cfg})
    sys.path.insert(0, os.environ["SERVICE_DIR"])
    sys.modules.pop("app", None)
    mod = importlib.import_module("app")
    from fastapi.testclient import TestClient
    return TestClient(mod.app)


def test_status_reads_replicas_without_writing(client):
    WRITES.clear(); READS.clear()
    r = client.get("/status/mysql")
    assert r.status_code == 200, r.text
    assert r.json() == {"store": "mysql", "namespace": "data-mesh", "replicas": 1}
    assert READS and READS[-1] == {"name": "mysql", "namespace": "data-mesh"}
    assert WRITES == []


def test_status_of_a_sleeping_store(client):
    r = client.get("/status/mongodb")
    assert r.status_code == 200 and r.json()["replicas"] == 0


def test_status_off_allowlist_is_400(client):
    WRITES.clear()
    r = client.get("/status/postgres")
    assert r.status_code == 400 and "allowlist" in str(r.json().get("detail"))
    assert WRITES == []


def test_cassandra_is_allowed_by_default(client):
    WRITES.clear()
    r = client.post("/scale", json={"store": "cassandra", "action": "wake"})
    assert r.status_code == 200 and r.json()["replicas"] == 1
    assert WRITES[-1]["name"] == "cassandra"
    s = client.get("/status/cassandra")
    assert s.status_code == 200 and s.json()["store"] == "cassandra"
