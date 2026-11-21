"""langfuse_evaluators.py (B255, 2026-11-20): the online evaluators' variable mappings, and reconciling them.

The judge (`wl-judge-oss`, gpt-oss:20b at an 8K window) cut a 10,596-token evaluator prompt: every rule mapped `query`
(and `context`) to the generation's whole Input, the message list with all the chunks inside, so a rule mapping both got
the chunks twice. The RAG services now record the bare question and the context text as generation metadata; each rule
reads only what it needs. Hallucination keeps the full Input: its template has no context variable, and it needs the
context once. Reconcile used to skip any rule that existed, so a changed mapping never reached Langfuse; it now PATCHes
a drifted rule with `target` + `mapping` (the shape this Langfuse version accepts; probed on a disabled rule).
"""
import importlib.util
import json
import pathlib

import httpx
import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "langfuse_evaluators.py"


@pytest.fixture
def le(monkeypatch):
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    spec = importlib.util.spec_from_file_location("langfuse_evaluators", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _by_name(le):
    return {name: mapping for name, _ev, _scope, mapping in le.RULES}


def test_no_rule_sends_the_whole_input_twice(le):
    for name, mapping in _by_name(le).items():
        whole = [m for m in mapping if m["source"] == "input" and "jsonPath" not in m]
        assert len(whole) <= 1, f"{name} maps the whole Input more than once"


def test_question_only_evaluators_read_the_bare_question(le):
    rules = _by_name(le)
    for name in ("Relevance", "Helpfulness", "Conciseness", "Toxicity", "citation"):
        q = next(m for m in rules[name] if m["variable"] == "query")
        assert q == {"variable": "query", "source": "metadata", "jsonPath": "$.query"}, name


def test_context_evaluators_read_the_context_once_from_metadata(le):
    rules = _by_name(le)
    for name in ("Contextrelevance", "Faithfulness", "refusal"):
        ctx = [m for m in rules[name] if m["variable"] == "context"]
        assert ctx == [{"variable": "context", "source": "metadata", "jsonPath": "$.context"}], name


def test_hallucination_keeps_the_full_input(le):
    q = next(m for m in _by_name(le)["Hallucination"] if m["variable"] == "query")
    assert q == {"variable": "query", "source": "input"}


def _client(rules_live, calls):
    def handler(req):
        calls.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        if req.method == "GET" and req.url.path.endswith("/evaluators"):
            return httpx.Response(200, json={"data": [{"name": "citation"}, {"name": "refusal"}]})
        if req.method == "GET" and req.url.path.endswith("/evaluation-rules"):
            return httpx.Response(200, json={"data": rules_live})
        return httpx.Response(200, json={"id": "new"})
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://langfuse")


def test_reconcile_patches_a_drifted_rule_leaves_a_current_one_and_creates_a_missing_one(le):
    rules = _by_name(le)
    live = [{"id": "r1", "name": "Relevance", "mapping": [{"variable": "query", "source": "input"},
                                                         {"variable": "generation", "source": "output"}]},
            {"id": "r2", "name": "Faithfulness", "mapping": rules["Faithfulness"]}]
    calls = []
    le.reconcile(_client(live, calls))
    patches = [c for c in calls if c[0] == "PATCH"]
    assert patches == [("PATCH", "/api/public/unstable/evaluation-rules/r1",
                        {"target": "observation", "mapping": rules["Relevance"]})]
    created = {c[2]["name"] for c in calls if c[0] == "POST" and c[1].endswith("/evaluation-rules")}
    assert created == set(rules) - {"Relevance", "Faithfulness"}


def test_reconcile_treats_mapping_order_as_irrelevant(le):
    rules = _by_name(le)
    live = [{"id": f"r{i}", "name": n, "mapping": list(reversed(m))} for i, (n, m) in enumerate(rules.items())]
    calls = []
    le.reconcile(_client(live, calls))
    assert not [c for c in calls if c[0] in ("PATCH", "POST") and "evaluation-rules" in c[1]]
