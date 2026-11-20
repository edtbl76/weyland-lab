"""B253 (2026-11-20): the Realm evaluated against simpler shapes of itself, inside the deployed service.

`POST /eval/run {task, arm}` runs one task in one arm and reports what it cost:
  realm   — Gná routes, and a lead delegates to its members (the Realm as it is);
  routed  — Gná routes, and the chosen agent answers alone with its own tools (no delegation);
  single  — one generic agent holding every Realm tool, no routing.
Always free-only (the local lane, LiteLLM fallbacks off, and no paid tools), whatever the caller sends.
The counters ride the same callback hook as Langfuse (obs.lf_config), so measuring does not change what the agents do.
obs.py, fleet.py and evalrun.py are loaded from their files: conftest stubs obs and fleet by name."""
import asyncio
import importlib.util
import pathlib
import sys
import types

import pytest

_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, _DIR / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ev(monkeypatch):
    obs = _load("realm_obs_eval", "obs.py")
    monkeypatch.setitem(sys.modules, "obs", obs)
    mod = _load("realm_evalrun_under_test", "evalrun.py")
    return mod, obs


def _usage_result(inp, out):
    msg = types.SimpleNamespace(usage_metadata={"input_tokens": inp, "output_tokens": out})
    gen = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(generations=[[gen]])


# --- the counter ---------------------------------------------------------------------------------------------------
def test_the_counter_sums_tokens_llm_calls_tools_and_delegations(ev):
    mod, _ = ev
    c = mod.RunCounter()
    c.on_llm_end(_usage_result(100, 20))
    c.on_llm_end(_usage_result(50, 5))
    c.on_tool_start({"name": "grafana_search_dashboards"}, "{}")
    c.on_tool_start({"name": "delegate_to_saga"}, "{}")
    c.on_tool_start({"name": "trino_execute_query"}, "{}")
    assert c.as_dict() == {"input_tokens": 150, "output_tokens": 25, "llm_calls": 2, "tool_calls": 2,
                           "delegations": 1, "tools_used": ["grafana_search_dashboards", "trino_execute_query"],
                           "delegated_to": ["saga"]}


def test_a_completion_without_usage_still_counts_as_a_call(ev):
    mod, _ = ev
    c = mod.RunCounter()
    c.on_llm_end(types.SimpleNamespace(generations=[[types.SimpleNamespace(text="x")]]))
    assert c.as_dict()["llm_calls"] == 1 and c.as_dict()["input_tokens"] == 0


def test_lf_config_carries_the_counter_only_while_counting(ev):
    mod, obs = ev
    assert obs.lf_config({"recursion_limit": 50}) == {"recursion_limit": 50}   # nothing added outside a count
    with mod.counting() as c:
        cfg = obs.lf_config({"recursion_limit": 50})
        assert c in cfg["callbacks"] and cfg["recursion_limit"] == 50
    assert "callbacks" not in obs.lf_config({})


# --- the arms ------------------------------------------------------------------------------------------------------
def test_every_arm_runs_free_only(ev, monkeypatch):
    mod, _ = ev
    seen = []

    async def fake_dispatch(task, history=None, session_id=None):
        seen.append(mod.is_free_only())
        return "verdandi", "ans"

    async def fake_classify(task):
        seen.append(mod.is_free_only())
        return "saga"

    async def fake_solo(spec, task, history=None):
        seen.append(mod.is_free_only())
        return "ans"
    monkeypatch.setattr(mod.gna, "dispatch", fake_dispatch)
    monkeypatch.setattr(mod.gna, "classify", fake_classify)
    monkeypatch.setattr(mod, "run_solo", fake_solo)
    for arm in mod.ARMS:
        asyncio.run(mod.run_arm("q", arm))
    assert seen and all(seen)
    assert mod.is_free_only() is False   # and it ends with the request


def test_realm_arm_is_the_full_dispatch(ev, monkeypatch):
    mod, _ = ev

    async def fake_dispatch(task, history=None, session_id=None):
        return "verdandi", "the answer"
    monkeypatch.setattr(mod.gna, "dispatch", fake_dispatch)
    out = asyncio.run(mod.run_arm("why is grafana slow", "realm"))
    assert out["arm"] == "realm" and out["routed_to"] == "verdandi" and out["answer"] == "the answer"
    assert out["seconds"] >= 0 and "input_tokens" in out


def test_routed_arm_runs_the_chosen_agent_alone_even_a_lead(ev, monkeypatch):
    mod, _ = ev
    ran = {}

    async def fake_classify(task):
        return "verdandi"   # a lead

    async def fake_solo(spec, task, history=None):
        ran["key"] = spec.key
        return "solo answer"

    async def no_dispatch(*a, **k):
        raise AssertionError("routed must not delegate")
    monkeypatch.setattr(mod.gna, "classify", fake_classify)
    monkeypatch.setattr(mod.gna, "dispatch", no_dispatch)
    monkeypatch.setattr(mod, "run_solo", fake_solo)
    out = asyncio.run(mod.run_arm("q", "routed"))
    assert ran["key"] == "verdandi" and out["routed_to"] == "verdandi" and out["answer"] == "solo answer"


def test_single_arm_holds_every_realm_tool_family_and_no_router(ev, monkeypatch):
    mod, _ = ev
    from roster import ROSTER
    ran = {}

    async def fake_solo(spec, task, history=None):
        ran["spec"] = spec
        return "one agent"

    async def no_classify(task):
        raise AssertionError("single must not route")
    monkeypatch.setattr(mod.gna, "classify", no_classify)
    monkeypatch.setattr(mod, "run_solo", fake_solo)
    out = asyncio.run(mod.run_arm("q", "single"))
    every = {p for a in ROSTER for p in a.tool_prefixes}
    assert set(ran["spec"].tool_prefixes) == every and not ran["spec"].lead
    assert out["routed_to"] is None and out["answer"] == "one agent"


def test_an_unknown_arm_is_refused(ev):
    mod, _ = ev
    with pytest.raises(ValueError, match="arm"):
        asyncio.run(mod.run_arm("q", "swarm"))


def test_the_counts_are_per_run(ev, monkeypatch):
    mod, _ = ev

    async def fake_solo(spec, task, history=None):
        for h in mod.current_counters():
            h.on_llm_end(_usage_result(10, 1))
        return "a"
    monkeypatch.setattr(mod, "run_solo", fake_solo)
    first = asyncio.run(mod.run_arm("q", "single"))
    second = asyncio.run(mod.run_arm("q", "single"))
    assert first["input_tokens"] == 10 and second["input_tokens"] == 10


# --- free-only drops paid tools ------------------------------------------------------------------------------------
def test_free_only_drops_paid_tools(monkeypatch):
    obs = _load("realm_obs_fleet_paid", "obs.py")
    monkeypatch.setitem(sys.modules, "obs", obs)
    fleet = _load("realm_fleet_paid", "fleet.py")
    from budget import free_only
    fleet._all_tools = [types.SimpleNamespace(name=n) for n in
                        ("perplexity_search", "perplexity_ask", "trino_execute_query", "grafana_query")]
    paid = asyncio.run(fleet.tools_for(("perplexity", "trino")))
    assert {t.name for t in paid} == {"perplexity_search", "perplexity_ask", "trino_execute_query"}

    async def free():
        with free_only():
            return await fleet.tools_for(("perplexity", "trino"))
    assert {t.name for t in asyncio.run(free())} == {"trino_execute_query"}
