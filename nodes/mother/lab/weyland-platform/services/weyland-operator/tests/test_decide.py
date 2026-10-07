"""Tests for the decision-model SHADOW (B174).

On each incident sweep a decision model (Jev over TypeSafe's API, or Clef-flash served on rogueone — same API) is asked
which tool the operator should open with, and its pick is compared with the tool qwen actually called first. It is a
shadow: it must never change, slow or break the sweep, never send the API key in clear text, and every failure must be
COUNTED (an error is never recorded as agreement).
"""
import asyncio
import types

import httpx
import pytest

import decide

TOOLS = [("k8s_pods_list", "List all the Kubernetes pods\n   in the cluster"), ("status", "Lab health")]


def _msg(*names):
    return types.SimpleNamespace(tool_calls=[{"name": n, "args": {}} for n in names])


# --- reading the operator's own first tool off the agent trace ------------------------------------------------------

def test_first_tool_called_is_the_earliest_tool_call():
    msgs = [types.SimpleNamespace(tool_calls=None), _msg("k8s_pods_list"), _msg("k8s_pods_log")]
    assert decide.first_tool_called(msgs) == "k8s_pods_list"


def test_first_tool_called_is_none_when_the_agent_called_no_tool():
    assert decide.first_tool_called([types.SimpleNamespace(tool_calls=[]), types.SimpleNamespace()]) is None


# --- the request ----------------------------------------------------------------------------------------------------

def test_request_is_one_choice_question_over_the_tools():
    body = decide.request_body("rules", "Alert: X", TOOLS, model="jev-1.13.0")
    question = body["questions"]["tool"]
    assert body["model"] == "jev-1.13.0"
    assert body["state"] == {"operator_rules": "rules", "request": "Alert: X"}
    assert question["type"] == "choice"
    assert list(question["criteria"]) == ["k8s_pods_list", "status"]
    assert question["criteria"]["k8s_pods_list"] == "List all the Kubernetes pods in the cluster"   # whitespace folded


def test_request_truncates_long_tool_descriptions():
    body = decide.request_body("r", "q", [("t", "x" * 5000)], model="m")
    assert len(body["questions"]["tool"]["criteria"]["t"]) == decide.DESCRIPTION_CHARS


def test_api_key_is_sent_only_over_https():
    assert decide.headers("https://api.typesafe.ai/v1/systemone", "k")["Authorization"] == "Bearer k"
    assert "Authorization" not in decide.headers("http://192.168.1.230:8004/v1/systemone", "k")
    assert "Authorization" not in decide.headers("https://api.typesafe.ai/v1/systemone", "")


def test_backend_label_follows_the_model():
    assert decide.backend_of("jev-1.13.0") == "jev"
    assert decide.backend_of("clef-flash") == "clef"


# --- comparing ------------------------------------------------------------------------------------------------------

def test_outcome_agree_disagree_and_no_baseline():
    assert decide.outcome("k8s_pods_list", "k8s_pods_list") == "agree"
    assert decide.outcome("status", "k8s_pods_list") == "disagree"
    assert decide.outcome("status", None) == "no_baseline"   # qwen called no tool — nothing to agree with


# --- the shadow call: fail-safe, counted ----------------------------------------------------------------------------

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _counter(name, **labels):
    from prometheus_client import REGISTRY
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture
def shadow_on(monkeypatch):
    monkeypatch.setattr(decide, "URL", "https://api.typesafe.ai/v1/systemone")
    monkeypatch.setattr(decide, "MODEL", "jev-1.13.0")
    monkeypatch.setattr(decide, "API_KEY", "test-key")


def test_shadow_records_agreement_and_spend(shadow_on):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"answers": {"tool": {"choice": "k8s_pods_list", "confidence": 0.8}},
                                         "usage": {"input_tokens": 1500, "output_tokens": 0}})

    before = _counter("operator_decide_shadow_total", backend="jev", outcome="agree", confident="true")
    tokens = _counter("operator_decide_input_tokens_total", backend="jev")

    async def go():
        async with _client(handler) as client:
            return await decide.shadow(client, "rules", "Alert: X", TOOLS, actual="k8s_pods_list", alert="X")

    result = asyncio.run(go())
    assert result["choice"] == "k8s_pods_list" and result["outcome"] == "agree"
    assert seen["auth"] == "Bearer test-key"
    assert _counter("operator_decide_shadow_total", backend="jev", outcome="agree", confident="true") == before + 1
    assert _counter("operator_decide_input_tokens_total", backend="jev") == tokens + 1500


@pytest.mark.parametrize("response", [
    httpx.Response(402, json={"error": "insufficient credit"}),     # the credit ran out
    httpx.Response(200, json={"answers": {}}),                       # a reply without the answer
    httpx.Response(200, text="not json"),
])
def test_shadow_never_raises_and_counts_an_error(shadow_on, response):
    before = _counter("operator_decide_shadow_total", backend="jev", outcome="error", confident="false")

    async def go():
        async with _client(lambda _r: response) as client:
            return await decide.shadow(client, "rules", "Alert: X", TOOLS, actual="status", alert="X")

    assert asyncio.run(go()) is None
    assert _counter("operator_decide_shadow_total", backend="jev", outcome="error", confident="false") == before + 1


def test_shadow_survives_a_network_failure(shadow_on):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    async def go():
        async with _client(handler) as client:
            return await decide.shadow(client, "rules", "q", TOOLS, actual=None, alert="X")

    assert asyncio.run(go()) is None


def test_shadow_refuses_a_non_http_url(monkeypatch):
    monkeypatch.setattr(decide, "URL", "file:///etc/passwd")

    async def go():
        async with _client(lambda _r: httpx.Response(200, json={})) as client:
            return await decide.shadow(client, "r", "q", TOOLS, actual=None, alert="X")

    assert asyncio.run(go()) is None


def test_enabled_only_when_switched_on(monkeypatch):
    monkeypatch.setattr(decide, "SHADOW", False)
    assert not decide.enabled()
    monkeypatch.setattr(decide, "SHADOW", True)
    assert decide.enabled()
