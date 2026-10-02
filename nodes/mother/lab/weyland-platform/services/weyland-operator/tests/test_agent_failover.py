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

    def __init__(self, llm):
        self.model = llm.model
        self.calls = 0
        self.fail = False

    async def ainvoke(self, _state):
        self.calls += 1
        if self.fail:
            raise TimeoutError(f"{self.model} stalled")
        return {"messages": [types.SimpleNamespace(content=f"answer from {self.model}", tool_calls=[])]}


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
                   _module("langgraph.prebuilt", create_react_agent=lambda llm, _tools: _FakeAgent(llm)))
        mp.setitem(sys.modules, "fleet", _module("fleet", load_fleet_tools=lambda: []))
        mp.setitem(sys.modules, "realm", _module("realm", REALM_TOOLS=[]))
        mp.setitem(sys.modules, "tools", _module("tools", READ_TOOLS=[], ACT_TOOLS=[]))
        mp.setitem(sys.modules, "prompts", _module("prompts", load_prompt=lambda _n, fallback: fallback))
        spec = importlib.util.spec_from_file_location("operator_agent_under_test", os.path.join(_HERE, "agent.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod


@pytest.fixture
def brains(agent_mod, monkeypatch):
    """Fresh call counters, and a switch for whether the local engine passes its health pre-check."""
    agent_mod._local_agent.calls = agent_mod._fallback_agent.calls = 0
    agent_mod._local_agent.fail = False
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
    assert agent._local_agent.calls == 0          # a failed pre-check does not even try the local engine


def test_without_fallback_a_local_error_mid_request_is_local_unavailable_not_haiku(brains):
    agent, _ = brains
    agent._local_agent.fail = True
    with pytest.raises(agent.LocalUnavailable, match="stalled"):
        asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert agent._fallback_agent.calls == 0


def test_without_fallback_a_healthy_local_engine_answers(brains):
    agent, _ = brains
    reply, _ = asyncio.run(agent.run("investigate", [], allow_fallback=False))
    assert reply == "answer from qwen2.5:7b"
    assert agent._fallback_agent.calls == 0


def test_a_person_chatting_still_fails_over_to_haiku(brains):
    agent, state = brains
    state["healthy"] = False
    reply, _ = asyncio.run(agent.run("what is broken?", []))
    assert reply == "answer from claude-haiku"
    assert agent._fallback_agent.calls == 1
