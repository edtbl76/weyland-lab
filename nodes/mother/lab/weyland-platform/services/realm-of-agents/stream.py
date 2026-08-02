"""Live execution stream — the Realm Console's data source (B17 UI, Phase 1 spike).

The console wants a Studio-like inline trace tree of what's *actually happening*: Gná routes → a lead runs → it
delegates to members → members call tools, all with inputs/outputs/timings/tokens. That data already exists: our agents
ARE LangGraph graphs, and `graph.astream_events(version="v2")` emits every node / LLM / tool event with a `run_id` and
`parent_ids` (the nesting). This module runs a route under astream_events and normalizes each event to a compact wire
schema the browser can build a tree from:

    {type, id, parents[], name, ...}   type ∈ route_start·route·node_start·node_end·tool_start·tool_end·
                                                llm_start·llm_end·token·final·done·error

THE THING THIS SPIKE PROVES: whether the events of a lead's DELEGATED member sub-graph (Odin → Brokkr → its tool)
surface here nested under the delegate tool call, or only the top level. astream_events propagates through nested
runnables via LangChain's async callback context, and our delegate tool awaits `run_solo` in that same context — so it
*should* nest. Curl `/route/stream` on a delegating task and read the indented tree to confirm.
"""
import json

import agents
import realms
import router as gna
from roster import BY_KEY

_CONFIG = {"recursion_limit": 50}


def _short(v, n: int = 600) -> str:
    try:
        s = v if isinstance(v, str) else json.dumps(v, default=str)
    except Exception:
        s = str(v)
    return s if len(s) <= n else s[:n] + "…"


def _normalize(ev: dict) -> dict | None:
    """One LangGraph astream_events(v2) event → one compact wire event (or None to drop). Tokens are handled in
    _agent_events (they need delegate context). Pure LangGraph scaffolding (RunnableSequence/Prompt/should_continue/…)
    is dropped by keeping only the OUTERMOST graph's chain boundary — the one node_start the UI needs to anchor its tree."""
    et = ev.get("event")
    data = ev.get("data") or {}
    parents = ev.get("parent_ids", [])
    base = {"id": ev.get("run_id"), "parents": parents, "name": ev.get("name")}
    if et == "on_tool_start":
        return {**base, "type": "tool_start", "input": _short(data.get("input"))}
    if et == "on_tool_end":
        return {**base, "type": "tool_end", "output": _short(data.get("output"))}
    if et == "on_chat_model_start":
        return {**base, "type": "llm_start"}
    if et == "on_chat_model_end":
        return {**base, "type": "llm_end"}
    if et == "on_chain_start" and not parents:
        return {**base, "type": "node_start"}
    return None


async def _agent_events(spec, task: str, history):
    """Stream one agent's run (solo or lead) as normalized events; ends with a `final` carrying the answer.
    The answer is the LAST *root-level* LLM completion (not running inside any delegate_to_* sub-graph) — robust to the
    concurrent, nested fan-out — and its tokens stream to the answer pane, guarded by answer_reset so only the final
    synthesis turn is shown (a delegating turn emits tool-calls, not text, so it contributes nothing)."""
    if spec.lead:
        graph = await realms._lead_graph(spec)
        inp = {"messages": realms._lead_messages(spec, task, history)}
    else:
        graph = await agents._graph(spec)
        inp = {"messages": agents._solo_messages(spec, task, history)}
    delegate_ids, final = set(), None
    async for ev in graph.astream_events(inp, _CONFIG, version="v2"):
        et = ev.get("event")
        rid = ev.get("run_id")
        parents = ev.get("parent_ids", [])
        root_level = not (set(parents) & delegate_ids)
        if et == "on_tool_start" and (ev.get("name") or "").startswith("delegate_to_"):
            delegate_ids.add(rid)
        elif et == "on_chat_model_start" and root_level:
            yield {"type": "answer_reset"}
        elif et == "on_chat_model_stream" and root_level:
            txt = getattr((ev.get("data") or {}).get("chunk"), "content", "") or ""
            if txt:
                yield {"id": rid, "parents": parents, "type": "token", "text": txt}
            continue
        elif et == "on_chat_model_end" and root_level:
            txt = getattr((ev.get("data") or {}).get("output"), "content", None)
            if txt:
                final = txt
        n = _normalize(ev)
        if n:
            yield n
    yield {"type": "final", "answer": final or ""}


async def dispatch_events(task: str, history=None):
    """The full route as a live event stream: Gná's pick, then the chosen agent's (possibly nested) execution."""
    yield {"type": "route_start"}
    key = await gna.classify(task)
    spec = BY_KEY[key]
    yield {"type": "route", "agent": key, "god": spec.god, "role": spec.role, "realm": spec.realm}
    async for ev in _agent_events(spec, task, history):
        yield ev
    yield {"type": "done", "agent": key}
