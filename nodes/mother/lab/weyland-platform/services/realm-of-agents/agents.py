"""Build and run a single agent from its spec.

An agent is a LangGraph ReAct loop: brain (its `wl-*` lane) + its tool slice + its role prompt. Graphs are built lazily
on first use (tools load async from the Bifrost VK) and cached. Realm leads add delegation on top of this — see realms.py."""
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from budget import is_free_only
from fleet import tools_for
from llm import brain, effective_model
from obs import lf_config, log
from prompts import load_role
from roster import AgentSpec

# Keyed by (agent, free-only): the brain is baked into the graph, so a free-only run must never reuse a paid graph.
_graphs: dict[tuple[str, bool], object] = {}


async def _graph(spec: AgentSpec, tools: list | None = None, pre_model_hook=None):
    if tools is not None or pre_model_hook is not None:
        # A per-request graph (the B255 evaluation trials: a retrieved tool subset, or a context-editing hook). Never
        # cached: the tools differ per task. Building one is cheap; the tools themselves are already loaded.
        if tools is None:
            tools = await tools_for(spec.tool_prefixes)
        return create_react_agent(brain(spec.lane), tools, pre_model_hook=pre_model_hook)
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


async def run_solo(spec: AgentSpec, task: str, history: list | None = None, *, tools: list | None = None,
                   pre_model_hook=None) -> str:
    """Run `spec` on `task` as a standalone specialist. Returns its final text. `tools` replaces the spec's tool slice
    and `pre_model_hook` edits what the model sees before each call (both only for the B255 trial arms)."""
    graph = await _graph(spec, tools, pre_model_hook)
    log(f"{spec.god} · {spec.role} — thinking ({effective_model(spec.lane)})")
    result = await graph.ainvoke({"messages": _solo_messages(spec, task, history)}, lf_config({"recursion_limit": 50}))
    out = result["messages"][-1].content
    log(f"{spec.god} — answered ({len(out)} chars)")
    return out


def _find_tool(picker) -> StructuredTool:
    def find_tools(need: str) -> str:
        return picker.find(need)
    return StructuredTool.from_function(
        find_tools, name="find_tools",
        description=("Find more tools when the ones you have cannot do what the task needs. Describe the need in a few "
                     "words (for example 'list kubernetes pods' or 'query prometheus metrics'); the tools found are "
                     "yours from your next step."))


async def run_solo_retrieving(spec: AgentSpec, task: str, picker) -> str:
    """B255 trial arm single-rs (2026-11-22): `spec` on `task` holding only `picker.selected` plus find_tools, which
    grows the selection mid-run (langgraph-bigtool's pattern). The tool node can run every tool; the model is re-bound
    to the current selection before each call, so it only sees (and pays for) the tools it holds."""
    find = _find_tool(picker)
    chat = brain(spec.lane)

    def model(state, runtime):
        return chat.bind_tools([*picker.selected, find])
    graph = create_react_agent(model, [*picker.tools, find])
    log(f"{spec.god} · {spec.role} — thinking with {len(picker.selected)} retrieved tools "
        f"({effective_model(spec.lane)})")
    result = await graph.ainvoke({"messages": _solo_messages(spec, task)}, lf_config({"recursion_limit": 50}))
    out = result["messages"][-1].content
    log(f"{spec.god} — answered ({len(out)} chars; found {len(picker.found)} more tools)")
    return out
