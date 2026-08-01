"""Realm leads and delegation — the intra-realm A2A.

A lead (Odin, Kvasir, Verðandi, Tyr) supervises its members. We wire delegation the LangGraph-native way: each member
becomes a *tool* on the lead's ReAct loop (`delegate_to_<member>`), so the lead reasons about the task and calls the
right specialist — a real 2-hop delegation (Operator → Odin → Brokkr), not a flat dispatch. Members run via
agents.run_solo. Leads with no need to delegate just answer directly.

Cross-realm and up-to-Operator calls go over the A2A Protocol (Agent Cards) — served by app.py — not through this graph."""
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents import run_solo
from llm import brain
from prompts import load_role
from roster import BY_KEY, AgentSpec

_leads: dict[str, object] = {}


def _member_tool(member: AgentSpec) -> StructuredTool:
    async def _call(task: str) -> str:
        # A member failing (e.g. an empty LLM completion) is DATA for the lead to reconcile, not a crash that takes
        # down the whole route. Also guard an empty delegated task — some models call the tool with no arg, and an
        # empty user turn makes several providers return zero choices (→ IndexError deep in langchain_core).
        try:
            return await run_solo(member, task or f"Handle your part ({member.role}) of the current objective.")
        except Exception as exc:
            return f"[{member.god} ({member.role}) could not complete the sub-task: {exc}]"
    return StructuredTool.from_function(
        coroutine=_call,
        name=f"delegate_to_{member.key}",
        description=f"Delegate to {member.god} ({member.role}): {member.what}",
    )


async def _lead_graph(lead: AgentSpec):
    g = _leads.get(lead.key)
    if g is None:
        member_tools = [_member_tool(BY_KEY[k]) for k in lead.members if k in BY_KEY]
        g = create_react_agent(brain(lead.lane), member_tools)
        _leads[lead.key] = g
    return g


async def run_lead(lead: AgentSpec, task: str, history: list | None = None) -> str:
    """Run a realm lead: it decomposes the task and delegates to its members, then reconciles their outputs."""
    graph = await _lead_graph(lead)
    sys = (load_role(lead) + " You lead a team of specialists — call delegate_to_* tools to hand each sub-task to the "
           "right member, then synthesize their results into one answer. Do the work through them, not yourself.")
    messages = [("system", sys)]
    if history:
        messages += history
    messages.append(("user", task))
    result = await graph.ainvoke({"messages": messages})
    return result["messages"][-1].content
