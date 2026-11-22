"""langfuse_evaluators.py (B255, 2026-11-20): the online evaluators' variable mappings, and reconciling them.

The judge (`wl-judge-oss`, gpt-oss:20b at an 8K window) cut a 10,596-token evaluator prompt: every rule mapped `query`
(and `context`) to the generation's whole Input, the message list with all the chunks inside, so a rule mapping both got
the chunks twice. The RAG services now record the bare question and the context text as generation metadata; each rule
reads only what it needs. Hallucination keeps the full Input: its template has no context variable, and it needs the
context once. Reconcile used to skip any rule that existed, so a changed mapping never reached Langfuse; it now PATCHes
a drifted rule with `target` + `mapping` (the shape this Langfuse version accepts; probed on a disabled rule).
"""
import importlib.util
import pathlib

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


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


class _Client:
    """The three calls reconcile makes, recorded. A plain fake on purpose: another test in this suite replaces
    `httpx` in sys.modules with a stub (test_ollama_auth.py), so httpx.MockTransport is not reliably there."""

    def __init__(self, rules_live, calls):
        self.rules_live, self.calls = rules_live, calls

    def get(self, path, **kw):
        self.calls.append(("GET", path, None))
        if path.endswith("/evaluators"):
            return _Resp({"data": [{"name": "citation"}, {"name": "refusal"}]})
        return _Resp({"data": self.rules_live})

    def post(self, path, json=None, **kw):
        self.calls.append(("POST", path, json))
        return _Resp({"id": "new"})

    def patch(self, path, json=None, **kw):
        self.calls.append(("PATCH", path, json))
        return _Resp({"id": path.rsplit("/", 1)[-1]})


def _client(rules_live, calls):
    return _Client(rules_live, calls)


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


def test_a_slow_patch_is_reported_and_does_not_stop_the_rest(le, capsys):
    # Live, 2026-11-21: the first rollout's PATCH of `Conciseness` timed out (60 s) and the uncaught error stopped the
    # run, leaving six rules on the old mapping (two judge prompts were then cut). One slow call must not abort the rest.
    rules = _by_name(le)
    live = [{"id": f"r{i}", "name": n, "mapping": [{"variable": "x", "source": "input"}]} for i, n in enumerate(rules)]
    calls = []
    client = _Client(live, calls)
    real_patch = client.patch

    def flaky_patch(path, json=None, **kw):
        if path.endswith("/r0"):
            raise TimeoutError("timed out")
        return real_patch(path, json=json, **kw)
    client.patch = flaky_patch
    with pytest.raises(SystemExit) as stop:   # a partial reconcile is a failure, loudly (the asset run shows red)
        le.reconcile(client)
    assert stop.value.code == 1
    patched = {c[1].rsplit("/", 1)[-1] for c in calls if c[0] == "PATCH"}
    assert patched == {f"r{i}" for i in range(1, len(rules))}
    out = capsys.readouterr().out
    assert "rule mapping update FAILED" in out and "TimeoutError" in out and "rerun" in out
