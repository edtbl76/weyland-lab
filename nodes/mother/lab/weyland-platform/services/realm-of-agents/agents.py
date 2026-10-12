"""Build and run a single agent from its spec.

An agent is a LangGraph ReAct loop: brain (its `wl-*` lane) + its tool slice + its role prompt. Graphs are built lazily
on first use (tools load async from the Bifrost VK) and cached. Realm leads add delegation on top of this — see realms.py."""
from langgraph.prebuilt import create_react_agent

from budget import is_free_only
from fleet import tools_for
from llm import brain, effective_model
from obs import lf_config, log
from prompts import load_role
from roster import AgentSpec

# Keyed by (agent, free-only): the brain is baked into the graph, so a free-only run must never reuse a paid graph.
_graphs: dict[tuple[str, bool], object] = {}


async def _graph(spec: AgentSpec):
    cache_key = (spec.key, is_free_only())
    g = _graphs.get(cache_key)
    if g is None:
        tools = await tools_for(spec.tool_prefixes)
        g = create_react_agent(brain(spec.lane), tools)
        _graphs[cache_key] = g
    return g


def _solo_messages(spec: AgentSpec, task: str, history: list | None = None) -> list:
    """The message list for a solo run — reused by run_solo AND the streaming path (stream.py), so they can't drift."""
    messages = [("system", load_role(spec))]
    if history:
        messages += history
    messages.append(("user", task))
    return messages


async def run_solo(spec: AgentSpec, task: str, history: list | None = None) -> str:
    """Run `spec` on `task` as a standalone specialist. Returns its final text."""
    graph = await _graph(spec)
    log(f"{spec.god} · {spec.role} — thinking ({effective_model(spec.lane)})")
    result = await graph.ainvoke({"messages": _solo_messages(spec, task, history)}, lf_config({"recursion_limit": 50}))
    out = result["messages"][-1].content
    log(f"{spec.god} — answered ({len(out)} chars)")
    return out
