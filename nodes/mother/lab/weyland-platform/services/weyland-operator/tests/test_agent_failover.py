"""Tests for the operator's brain routing — local primary, paid Haiku failover (2026-10-02).

What these pin down: an automatic caller (the incident sweep) passes `allow_fallback=False` and must NEVER reach the
paid Haiku brain — when the local engine is down or fails mid-request it gets `LocalUnavailable` and retries later. A
person chatting keeps the failover. Found 2026-10-02: during eval runs Ollama on rogueone was busy, sweeps failed over
to Haiku, and Haiku handed work to the Realm of Agents (which also runs on paid Haiku) — $12.44 in 14 days on a $0
budget.

agent.py compiles both agents at import (langgraph, langchain_openai, the MCP fleet), so its heavy imports are stubbed
here and the real module is loaded from its file under a private name. The stubs stand in for the LLM; what is tested
is run()'s own routing decision.
"""
import asyncio
import importlib.util
import os
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _FakeLLM:
    def __init__(self, **kw):
        self.model = kw["model"]


class _FakeAgent:
    """Records each invoke; `fail` makes it raise like a stalled or erroring local engine."""

    def __init__(self, llm, tools=(), pre_model_hook=None):
        self.model = llm.model
        self.tools = list(tools)
        self.pre_model_hook = pre_model_hook
        self.calls = 0
        self.fail = False
        self.empty = False      # answer with no text, as qwen2.5:7b does after a fleet tool call (2026-10-03)
        self.trace = []         # earlier messages in the run (e.g. a propose_act tool call)

    async def ainvoke(self, _state):
        self.calls += 1
        if self.fail:
            raise TimeoutError(f"{self.model} stalled")
        final = types.SimpleNamespace(content="" if self.empty else f"answer from {self.model}", tool_calls=[])
        return {"messages": self.trace + [final]}


FLEET_RESULTS = [None]   # import-time load: Keycloak not up yet (the 2026-10-01 restart)


def _module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


@pytest.fixture(scope="module")
def agent_mod():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("OPERATOR_LLM_FALLBACK", "1")
        mp.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        mp.setitem(sys.modules, "langchain_openai", _module("langchain_openai", ChatOpenAI=_FakeLLM))
        mp.setitem(sys.modules, "langgraph", _module("langgraph"))
        mp.setitem(sys.modules, "langgraph.prebuilt",
                   _module("langgraph.prebuilt", create_react_agent=lambda llm, tools, **kw: _FakeAgent(llm, tools, **kw)))
        # load_fleet_tools pops the next scripted result: a list = loaded, None = configured but failed (retry)
        mp.setitem(sys.modules, "fleet", _module("fleet", load_fleet_tools=lambda: FLEET_RESULTS.pop(0)))
        mp.setitem(sys.modules, "realm", _module("realm", REALM_TOOLS=[types.SimpleNamespace(name="delegate_to_realm")]))
        mp.setitem(sys.modules, "tools", _module("tools", READ_TOOLS=[], ACT_TOOLS=[]))
        mp.setitem(sys.modules, "prompts", _module("prompts", load_prompt=lambda _n, fallback: fallback))
        spec = importlib.util.spec_from_file_location("operator_agent_under_test", os.path.join(_HERE, "agent.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod


@pytest.fixture
def brains(agent_mod, monkeypatch):
    """Fresh call counters, and a switch for whether the local engine passes its health pre-check."""
    agent_mod._local_agent.calls = agent_mod._fallback_agent.calls = agent_mod._unpaid_agent.calls = 0
    for b in (agent_mod._local_agent, agent_mod._fallback_agent, agent_mod._unpaid_agent):
        b.fail = b.empty = False
        b.trace = []
    state = {"healthy": True}

    async def healthy():
        return state["healthy"]

    monkeypatch.setattr(agent_mod, "_local_healthy", healthy)
    return agent_mod, state


def test_without_fallback_a_down_local_engine_is_local_unavailable_not_haiku(brains):
    agent, state = brains
    state["healthy"] = False
    with pytest.raises(agent.LocalUnavailable):
        asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert agent._fallback_agent.calls == 0
    assert agent._unpaid_agent.calls == 0         # a failed pre-check does not even try the local engine


def test_without_fallback_a_local_error_mid_request_is_local_unavailable_not_haiku(brains):
    agent, _ = brains
    agent._unpaid_agent.fail = True
    with pytest.raises(agent.LocalUnavailable, match="stalled"):
        asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert agent._fallback_agent.calls == 0


def test_without_fallback_a_healthy_local_engine_answers(brains):
    agent, _ = brains
    reply, _ = asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert reply == "answer from qwen2.5:7b-operator"
    assert agent._fallback_agent.calls == 0


def test_a_person_chatting_still_fails_over_to_haiku(brains):
    agent, state = brains
    state["healthy"] = False
    reply, _ = asyncio.run(agent.run("what is broken?", []))
    assert reply == "answer from claude-haiku"
    assert agent._fallback_agent.calls == 1


# --- 2026-10-03: an EMPTY reply is a failure, never an answer ---------------------------------------------------------
# Found live: after any fleet tool call, qwen2.5:7b's final turn came back from Ollama as `{"content": ""}` (finish=stop,
# 40 tokens spent, no tool call). No exception, so no failover — the person got a blank reply and the metrics counted a
# local success. The engine itself is healthy, so an empty reply fails over THIS request without marking it down.


def test_a_person_chatting_gets_haiku_when_the_local_reply_is_empty(brains, monkeypatch):
    agent, _ = brains
    downs = []
    monkeypatch.setattr(agent, "_mark_local_down", lambda: downs.append(1))
    agent._local_agent.empty = True
    reply, _ = asyncio.run(agent.run("which pods are down?", []))
    assert reply == "answer from claude-haiku"
    assert agent._fallback_agent.calls == 1
    assert downs == []                            # a healthy engine with bad output stays primary for the next request


def test_without_fallback_an_empty_local_reply_is_empty_reply_not_haiku(brains, monkeypatch):
    # NOT LocalUnavailable: that defers the incident sweep to retry later, and this failure is persistent — the
    # incident would never be posted. EmptyReply lets the sweep post the alert with the reason. Still spends nothing.
    agent, _ = brains
    downs = []
    monkeypatch.setattr(agent, "_mark_local_down", lambda: downs.append(1))
    agent._unpaid_agent.empty = True
    with pytest.raises(agent.EmptyReply, match="empty reply"):
        asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert agent._fallback_agent.calls == 0
    assert downs == []


def test_when_both_brains_reply_empty_it_is_an_error_not_a_blank_answer(brains):
    agent, _ = brains
    agent._local_agent.empty = agent._fallback_agent.empty = True
    with pytest.raises(agent.EmptyReply, match="claude-haiku"):
        asyncio.run(agent.run("which pods are down?", []))


def test_whitespace_only_is_empty_too(brains):
    agent, _ = brains
    agent._unpaid_agent.empty = True
    agent._unpaid_agent.trace = []
    real = agent._unpaid_agent.ainvoke

    async def blank(state):
        out = await real(state)
        out["messages"][-1].content = "  \n"
        return out
    agent._unpaid_agent.ainvoke = blank
    try:
        with pytest.raises(agent.EmptyReply, match="empty reply"):
            asyncio.run(agent.run("investigate", [], allow_fallback=False))
    finally:
        del agent._unpaid_agent.ainvoke


def test_an_empty_reply_that_proposes_an_action_still_stands(brains):
    agent, _ = brains
    agent._local_agent.empty = True
    agent._local_agent.trace = [types.SimpleNamespace(content="", tool_calls=[
        {"name": "propose_act", "args": {"tool": "launch_job", "summary": "run ingestion", "job_name": "ingest"}}])]
    reply, proposal = asyncio.run(agent.run("run the ingestion pipeline", []))
    assert proposal == {"tool": "launch_job", "summary": "run ingestion", "job_name": "ingest"}
    assert agent._fallback_agent.calls == 0       # the app shows the confirm step from the proposal, not the text


# --- 2026-10-02: the fleet loads with retries, and the operator is not Ready until it has ----------------------------
# Found live: the pod restarted during the 2026-10-01 node stall, could not mint its Keycloak token, and ran 31h with
# ZERO fleet tools while /ready said ready — the load was one-shot at import.


def _tool(name):
    return types.SimpleNamespace(name=name)


def _names(brain):
    return [t.name for t in brain.tools if t.name != "delegate_to_realm"]


def test_a_failed_import_time_load_leaves_the_fleet_not_ready(agent_mod):
    assert agent_mod.fleet_ready() is False
    assert _names(agent_mod._local_agent) == [] and _names(agent_mod._fallback_agent) == []


def test_the_retry_loop_keeps_trying_until_the_fleet_loads_then_rebuilds_both_brains(agent_mod):
    FLEET_RESULTS[:] = [None, None, [_tool("k8s_pods_list"), _tool("grafana_list_teams")]]
    asyncio.run(asyncio.wait_for(agent_mod.fleet_retry_loop(interval=0), timeout=5))
    assert FLEET_RESULTS == []                                       # three attempts: two failures, then a load
    assert agent_mod.fleet_ready() is True
    assert _names(agent_mod._fallback_agent) == ["k8s_pods_list", "grafana_list_teams"]
    assert _names(agent_mod._local_agent) == ["k8s_pods_list"]                   # curated LOCAL_FLEET_ALLOW subset
    assert _names(agent_mod._unpaid_agent) == ["k8s_pods_list"]                  # the sweep's brain is rebuilt too


def test_the_retry_loop_returns_at_once_when_the_fleet_is_already_loaded(agent_mod):
    FLEET_RESULTS[:] = []                                            # any further load attempt would IndexError
    asyncio.run(asyncio.wait_for(agent_mod.fleet_retry_loop(interval=0), timeout=5))
    assert agent_mod.fleet_ready() is True


# --- 2026-10-02: the unpaid path also cannot reach the Realm ------------------------------------------------------------
# delegate_to_realm hands work to the Realm of Agents, which runs on the paid wl-agentic Haiku lane whichever brain
# calls it — $12.18 of the $12.44 found on 2026-10-02 came through it. So allow_fallback=False runs on a local brain
# compiled WITHOUT that tool; a person chatting keeps it.


def _tool_names(brain):
    return [t.name for t in brain.tools]


def test_the_unpaid_brain_has_no_delegate_to_realm(agent_mod):
    assert "delegate_to_realm" not in _tool_names(agent_mod._unpaid_agent)
    assert agent_mod._unpaid_agent.model == agent_mod.LOCAL_MODEL               # same free local model


def test_a_person_chatting_keeps_delegate_to_realm(agent_mod):
    assert "delegate_to_realm" in _tool_names(agent_mod._local_agent)
    assert "delegate_to_realm" in _tool_names(agent_mod._fallback_agent)


def test_the_local_brain_may_recall_shared_memory(agent_mod):
    # B182 (2026-10-03): the compositor fleet exposes the shared memory's read tools as memory_*; the local brain's
    # curated allowlist must admit the recall pair or the operator cannot use memory without paid Haiku.
    allow = agent_mod.LOCAL_FLEET_ALLOW
    assert any(a in "memory_search_notes" for a in allow)
    assert any(a in "memory_read_note" for a in allow)
    assert not any(a in "memory_build_context" for a in allow)   # curated: recall pair only


def test_without_fallback_the_unpaid_brain_answers_not_the_chat_brain(brains):
    agent, _ = brains
    asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert agent._unpaid_agent.calls == 1 and agent._local_agent.calls == 0


# --- 2026-10-04: the local brain's prompt must FIT its context window --------------------------------------------------
# Root cause of the empty replies: Ollama ran qwen2.5:7b with a ~2K-token window per request and silently cut the
# ~5-6.5K-token prompt ("truncating input prompt limit=2050 prompt=5979", 801x in 14 days). The fix is a 32K variant
# (nodes/rogueone/ollama/qwen2.5-7b-operator.Modelfile) plus a cap on tool results — one pod list was ~18K tokens.


class _Msg:
    """Stands in for a langchain message: `type` + pydantic-style model_copy (the slim test lane has no langchain)."""

    def __init__(self, type_, content):
        self.type, self.content = type_, content

    def model_copy(self, update):
        m = _Msg(self.type, self.content)
        m.__dict__.update(update)
        return m


def test_the_local_brain_defaults_to_the_32k_operator_model(agent_mod):
    assert agent_mod.LOCAL_MODEL == "qwen2.5:7b-operator"


def test_an_oversized_tool_result_is_capped_with_a_note_and_the_rest_pass_untouched(agent_mod):
    cap = agent_mod.LOCAL_TOOL_RESULT_CAP
    big, small, ai = _Msg("tool", "x" * (cap + 500)), _Msg("tool", "short"), _Msg("ai", "y" * (cap + 500))
    out = agent_mod._cap_tool_results({"messages": [big, small, ai]})["llm_input_messages"]
    assert out[0].content.startswith("x" * cap) and "truncated 500 more characters" in out[0].content
    assert out[1] is small and out[2] is ai                 # small tool results and model turns are never touched
    assert len(big.content) == cap + 500                    # the graph state keeps the full result; only the LLM input


def test_a_content_block_tool_result_is_measured_by_its_text(agent_mod):
    cap = agent_mod.LOCAL_TOOL_RESULT_CAP
    blocks = _Msg("tool", [{"type": "text", "text": "z" * (cap + 10)}])   # langchain-mcp-adapters returns blocks
    out = agent_mod._cap_tool_results({"messages": [blocks]})["llm_input_messages"]
    assert isinstance(out[0].content, str) and "truncated 10 more characters" in out[0].content


def test_only_the_local_brains_cap_tool_results(agent_mod):
    assert agent_mod._local_agent.pre_model_hook is agent_mod._cap_tool_results
    assert agent_mod._unpaid_agent.pre_model_hook is agent_mod._cap_tool_results
    assert agent_mod._fallback_agent.pre_model_hook is None     # Haiku has a 200K window — give it everything


def test_the_prompt_sends_recall_questions_to_shared_memory(agent_mod):
    assert "memory_search_notes" in agent_mod.SYSTEM and "memory_read_note" in agent_mod.SYSTEM
