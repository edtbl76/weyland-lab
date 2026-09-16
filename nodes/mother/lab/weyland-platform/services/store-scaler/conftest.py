"""Test harness for store-scaler/app.py.

app.py imports `from kubernetes import client, config` and, at module scope, calls `config.load_incluster_config()`
and builds `_apps = client.AppsV1Api()`. So stub the kubernetes module before import: load_incluster_config → no-op,
AppsV1Api → a fake that RECORDS patch_namespaced_deployment_scale calls (so the /scale success path is assertable
without a cluster). fastapi/pydantic are kept real — the tests drive real requests/responses via TestClient.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class _FakeApps:
    def __init__(self):
        self.calls = []

    def patch_namespaced_deployment_scale(self, name, namespace, body):
        self.calls.append({"name": name, "namespace": namespace, "body": body})
        return {"ok": True}


_k8s = types.ModuleType("kubernetes")
_client = types.ModuleType("kubernetes.client"); _client.AppsV1Api = _FakeApps
_config = types.ModuleType("kubernetes.config"); _config.load_incluster_config = lambda *a, **k: None
_k8s.client = _client
_k8s.config = _config
sys.modules["kubernetes"] = _k8s
sys.modules["kubernetes.client"] = _client
sys.modules["kubernetes.config"] = _config
