"""Realm leads and delegation — the intra-realm A2A.

A lead (Odin, Kvasir, Verðandi, Tyr) supervises its members. We wire delegation the LangGraph-native way: each member
becomes a *tool* on the lead's ReAct loop (`delegate_to_<member>`), so the lead reasons about the task and calls the
right specialist — a real 2-hop delegation (Operator → Odin → Brokkr), not a flat dispatch. Members run via
agents.run_solo. Leads with no need to delegate just answer directly.

Cross-realm and up-to-Operator calls go over the A2A Protocol (Agent Cards) — served by app.py — not through this graph."""
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from agents import run_solo
from fleet import tools_for
from llm import brain
from obs import log
from prompts import load_role
from roster import BY_KEY, AgentSpec

_leads: dict[str, object] = {}


def _member_tool(member: AgentSpec) -> StructuredTool:
    async def _call(task: str) -> str:
        # A member failing (e.g. an empty LLM completion) is DATA for the lead to reconcile, not a crash that takes
        # down the whole route. Also guard an empty delegated task — some models call the tool with no arg, and an
        # empty user turn makes several providers return zero choices (→ IndexError deep in langchain_core).
        log(f"  ↳ delegating to {member.god} ({member.role})")
        sub = task or f"Handle your part ({member.role}) of the current objective."
        try:
            # A member that is ITSELF a lead (e.g. the Operator delegating to Odin) must run AS a lead — keeping its own
            # delegate_to_* tools — so multi-level delegation works (Operator → Odin → Brokkr/Forseti). Running it solo
            # (the old behaviour) stripped those tools, so a delegated lead could only answer directly, never fan out.
            # run_lead is defined below in this module; the closure is called at runtime, so the reference resolves.
            return await (run_lead(member, sub) if member.lead else run_solo(member, sub))
        except Exception as exc:
            log(f"  ↳ {member.god} FAILED: {exc}")
            return f"[{member.god} ({member.role}) could not complete the sub-task: {exc}]"
    return StructuredTool.from_function(
        coroutine=_call,
        name=f"delegate_to_{member.key}",
        description=f"Delegate to {member.god} ({member.role}): {member.what}",
    )


async def _lead_graph(lead: AgentSpec):
    g = _leads.get(lead.key)
    if g is None:
        # A lead gets BOTH its own tools (so it can do its specialty directly — e.g. Verðandi's grafana_*) AND a
        # delegate_to_* tool per member (to hand off everything else). Two-mode: act on your specialty, delegate the rest.
        own_tools = await tools_for(lead.tool_prefixes)
        member_tools = [_member_tool(BY_KEY[k]) for k in lead.members if k in BY_KEY]
        g = create_react_agent(brain(lead.lane), own_tools + member_tools)
        _leads[lead.key] = g
    return g


def _lead_messages(lead: AgentSpec, task: str, history: list | None = None) -> list:
    """The message list for a lead run — reused by run_lead AND the streaming path (stream.py), so they can't drift.
    The lead is told to DELEGATE as its primary job (decompose → delegate_to_* every relevant member), because a
    capable model (Haiku) left to its own judgment just answers directly and the team never runs — so delegation is a
    mandate, not an option, and the lead is handed its explicit roster to remove any ambiguity about who to call."""
    team = ", ".join(f"{BY_KEY[k].god} ({BY_KEY[k].role})" for k in lead.members if k in BY_KEY)
    # The Operator (Root) routes ACROSS realms, and its realm-lead members' generic roles ("orchestrator", "strategy")
    # + the realm names don't self-describe their domain — so give it an explicit domain→realm map, or it misroutes
    # (e.g. an engineering task to Vanaheim/Kvasir instead of Valhalla/Odin). Realm leads don't need this (their members
    # are all one discipline).
    routing = ""
    if lead.realm == "Root":
        routing = (" Choose the realm(s) by the task's DOMAIN: **engineering** — architecture, code, tests, deploy, "
                   "security, code review → Valhalla (Odin); **knowledge / strategy / consulting / delivery** → "
                   "Vanaheim (Kvasir); **data & platform** — observability, SQL, data quality, lineage, catalog → "
                   "Midgard (Verðandi); **research, evaluation & safety** — scoring, RAG, web research, summaries, "
                   "guardrails → the Well (Tyr). Delegate to every realm the task genuinely spans, and NOT the others.")
    sys = (load_role(lead) + f" You are a LEAD; your team is: {team}. Your PRIMARY job is to DELEGATE, not to do the "
           "work yourself. DECOMPOSE the objective into sub-tasks and, for EACH one, call the matching "
           "delegate_to_<member> tool to hand it to the right specialist — delegate to EVERY member whose expertise the "
           "task touches, not just one." + routing + " Use your OWN tools only for your personal specialty; do NOT "
           "answer a specialist's sub-task yourself when a member exists for it. Only AFTER your members return do you "
           "synthesize their work and yours into one final answer.")
    messages = [("system", sys)]
    if history:
        messages += history
    messages.append(("user", task))
    return messages


async def run_lead(lead: AgentSpec, task: str, history: list | None = None) -> str:
    """Run a realm lead: it does its own specialty with its own tools, delegates the rest to its members, and reconciles."""
    log(f"{lead.god} (lead) — decomposing and delegating")
    graph = await _lead_graph(lead)
    result = await graph.ainvoke({"messages": _lead_messages(lead, task, history)}, {"recursion_limit": 50})
    return result["messages"][-1].content
