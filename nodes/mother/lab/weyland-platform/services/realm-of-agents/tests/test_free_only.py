"""The free-only request mode (2026-10-12).

Every Realm brain is the Haiku-backed `wl-agentic` lane, so an AUTOMATIC caller (the ship-images Realm transaction)
must be able to run the whole Realm — Gná's routing, the agent graph, its tools — on a FREE brain instead: `wl-local`
(the operator's resident qwen2.5:7b on rogueone, B222 2026-10-22; it was `wl-judge` until that lane moved to qwen3:14b)
with LiteLLM's fallbacks DISABLED, so "free" never depends on a fallback chain staying free. The mode is a ContextVar set per request (budget.free_only), so it follows the
async call into nested agents and never leaks into a person's next request. Graphs are cached per (agent, mode), so a
free run never reuses a paid graph and vice versa.
"""
import asyncio
import importlib.util
import os
import sys
import types

import budget

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_real(name, stubs):
    """Import the REAL `<name>.py` under a private module name (conftest stubs the sibling of the same name)."""
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(f"_real_{name}", os.path.join(_ROOT, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class _Chat:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _llm():
    return _load_real("llm", {"langchain_openai": types.SimpleNamespace(ChatOpenAI=_Chat)})


def test_a_person_gets_the_configured_hosted_brain():
    llm = _llm()
    b = llm.brain("wl-coding")
    assert b.kwargs["model"] == "wl-agentic"
    assert "extra_body" not in b.kwargs


def test_free_only_uses_the_free_local_lane_with_fallbacks_disabled():
    llm = _llm()
    with budget.free_only():
        b = llm.brain("wl-coding")
        assert llm.effective_model("wl-coding") == "wl-local"
    assert b.kwargs["model"] == "wl-local"
    assert b.kwargs["extra_body"] == {"disable_fallbacks": True}


def test_the_mode_ends_with_the_request():
    llm = _llm()
    with budget.free_only():
        assert budget.is_free_only()
    assert not budget.is_free_only()
    assert llm.brain("wl-coding").kwargs["model"] == "wl-agentic"


def test_the_mode_follows_the_call_into_a_nested_task():
    async def nested():
        return budget.is_free_only()

    async def run():
        with budget.free_only():
            return await asyncio.create_task(nested())

    assert asyncio.run(run()) is True


def test_the_image_copies_every_service_module():
    # The Dockerfile COPYs an explicit file list; budget.py was missing from it on 2026-10-12, which would have
    # crashed the Realm at import. Every service module (not the test harness) must be in the image.
    import re
    dockerfile = open(os.path.join(_ROOT, "Dockerfile")).read()
    copied = set(re.findall(r"\b([a-z_0-9]+\.py)\b", dockerfile))
    modules = {f for f in os.listdir(_ROOT) if f.endswith(".py") and f != "conftest.py"}
    assert modules - copied == set()


def test_agent_graphs_are_cached_per_mode():
    built = []

    def fake_build(brain, tools):
        built.append(brain)
        return object()

    fake_llm = types.SimpleNamespace(brain=lambda lane: ("free" if budget.is_free_only() else "paid", lane),
                                     effective_model=lambda lane: lane)
    async def no_tools(_prefixes):
        return []

    agents = _load_real("agents", {"langgraph.prebuilt": types.SimpleNamespace(create_react_agent=fake_build),
                                   "llm": fake_llm, "fleet": types.SimpleNamespace(tools_for=no_tools)})
    spec = types.SimpleNamespace(key="huginn", lane="wl-coding", tool_prefixes=())

    async def graphs():
        paid = await agents._graph(spec)
        with budget.free_only():
            free = await agents._graph(spec)
            free_again = await agents._graph(spec)
        return paid, free, free_again, await agents._graph(spec)

    paid, free, free_again, paid_again = asyncio.run(graphs())
    assert paid is not free
    assert free is free_again and paid is paid_again
    assert built == [("paid", "wl-coding"), ("free", "wl-coding")]
