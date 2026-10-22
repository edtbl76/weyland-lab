"""Every Dagster call to Ollama presents the front-door token (B211, 2026-10-22).

rogueone's Ollama now sits behind a proxy that answers 401 to a remote caller without `Authorization: Bearer <token>`.
Dagster's runs execute in the dagster-user-code pod, so they are remote callers. A call site that forgets the header
fails only at run time: the eval matrix's drain would read "nothing resident" and race an eviction, the catalog would
drop every local model, the judge and the generator would error per item. These load each module with dagster and httpx
stubbed (the slim test lane has neither) and record the headers each call sends.
"""
import importlib.util
import os
import sys
import types

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weyland-dagster/


class _Subscriptable:
    def __class_getitem__(cls, item):
        return cls


def _module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


class _Recorder:
    """Stands in for httpx: records each call's headers and answers like Ollama would."""

    def __init__(self):
        self.headers = []

    def _answer(self, url, **kw):
        self.headers.append((url, (kw.get("headers") or {}).get("Authorization")))
        body = {"models": [], "choices": [{"message": {"content": '{"questions": ["q?"]}'}}]}
        return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: body, status_code=200)

    def get(self, url, **kw):
        return self._answer(url, **kw)

    def post(self, url, **kw):
        return self._answer(url, **kw)


@pytest.fixture
def load(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "tok-123")
    monkeypatch.setitem(sys.modules, "httpx", _module("httpx", Client=object, get=None, post=None))
    monkeypatch.setitem(sys.modules, "dagster", _module(
        "dagster", asset=lambda *a, **k: (a[0] if a and callable(a[0]) and not k else (lambda f: f)),
        RetryPolicy=lambda *a, **k: None, get_dagster_logger=lambda *a, **k: None, Output=_Subscriptable,
        MetadataValue=type("MV", (), {"__getattr__": lambda s, n: (lambda *a, **k: None)})()))
    pkg = _module("weyland_pipeline")
    pkg.__path__ = [os.path.join(_ROOT, "weyland_pipeline")]
    monkeypatch.setitem(sys.modules, "weyland_pipeline", pkg)
    monkeypatch.setitem(sys.modules, "weyland_pipeline.resources",
                        _module("weyland_pipeline.resources", PostgresResource=type("PostgresResource", (), {})))
    monkeypatch.delitem(sys.modules, "weyland_pipeline.ollama_auth", raising=False)

    def _load(relpath):
        spec = importlib.util.spec_from_file_location(f"oa_{relpath.replace('/', '_')}",
                                                      os.path.join(_ROOT, "weyland_pipeline", relpath))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        rec = _Recorder()
        m.httpx = rec
        return m, rec
    return _load


def test_the_header_carries_the_token_and_defaults_to_the_old_placeholder(load, monkeypatch):
    oa, _ = load("ollama_auth.py")
    assert oa.ollama_headers() == {"Authorization": "Bearer tok-123"}
    monkeypatch.delenv("OLLAMA_API_KEY")
    assert oa.ollama_headers() == {"Authorization": "Bearer ollama"}   # before the secret exists, nothing changes


def test_drain_gpu_presents_the_token(load):
    gpu, rec = load("gpu.py")
    gpu.drain_gpu("http://ollama:11434/v1", timeout_s=0)
    assert rec.headers and all(h == "Bearer tok-123" for _, h in rec.headers)


def test_the_model_catalog_presents_the_token(load):
    mc, rec = load("assets/model_catalog.py")
    mc._ollama()
    assert [h for _, h in rec.headers] == ["Bearer tok-123"]


def test_the_question_generator_presents_the_token(load):
    ets, rec = load("assets/eval_testset.py")
    ets._generate_questions([{"name": "n", "text": "t"}], 1)
    assert rec.headers and all(h == "Bearer tok-123" for _, h in rec.headers)


def test_the_judge_presents_the_token(load, monkeypatch):
    monkeypatch.setitem(sys.modules, "weyland_pipeline.structure",
                        _module("weyland_pipeline.structure", validate_scores=lambda *a, **k: ({}, "stub")))
    es, _ = load("assets/eval_scores.py")
    client = _Recorder()
    es._judge(client, "qwen3:14b", "q", ["c"], "a")
    assert [h for _, h in client.headers] == ["Bearer tok-123"]
