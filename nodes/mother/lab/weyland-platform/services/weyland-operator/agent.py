"""The operator agent — a LangGraph ReAct loop over the tool-server tools (B66 Part 1).

Uses LangGraph's prebuilt `create_react_agent` (handles reason → call tool → observe → repeat → answer). The brain is
local **gpt-oss:20b** via Ollama (the B66 bake-off proved it ties Claude Haiku on this exact workload, incl. the
act-path safety test). Read-only for now; act tools + the confirm-step land in Part 3."""
import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from prompts import load_prompt
from tools import ACT_TOOLS, READ_TOOLS
from fleet import build_router_tools, load_fleet_tools

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

SYSTEM = (
    "You are the weyland homelab operator. ALWAYS answer by calling a tool and reporting its result — NEVER tell the "
    "user to run kubectl/SQL/curl themselves; YOU run it. Base tools: status, context_search, context_ask (knowledge "
    "base). For lab subsystems, call the matching router with a natural-language request: `k8s` (cluster: pods, "
    "namespaces, events), `trino` (lakehouse SQL / catalogs), `grafana` (dashboards, Prometheus), `neo4j` (graph), "
    "`datahub` (catalog/lineage), `postgres` (Postgres). To CHANGE lab state (trigger a pipeline, run/score evals) you "
    "cannot act directly — call propose_act and the user confirms; never claim an action ran. Keep replies short (Telegram)."
)

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)
# Two-stage routing: the fleet's ~91 read tools collapse to 6 subsystem ROUTERS (each delegates to a focused sub-agent),
# so the top agent chooses among ~10 tools — within gpt-oss:20b's ceiling. Empty if the fleet is unreachable.
_FLEET_ROUTERS = build_router_tools(load_fleet_tools(), _llm)
_agent = create_react_agent(_llm, READ_TOOLS + _FLEET_ROUTERS + ACT_TOOLS)


def _extract_proposal(msgs: list) -> dict | None:
    """Return the most recent propose_act tool-call args, or None. The LLM can only propose — the app decides to
    fire — so we read the proposal off the trace rather than trusting the final text."""
    for m in reversed(msgs):
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") == "propose_act":
                args = dict(tc.get("args") or {})
                return {"tool": args.get("tool"), "summary": args.get("summary", ""),
                        "job_name": args.get("job_name", "")}
    return None


async def run(message: str, history: list | None = None) -> tuple[str, dict | None]:
    """Run the operator on a user message (+ optional prior [(role, text)] turns). Returns (reply, proposal) where
    proposal is a propose_act payload if the agent proposed an action, else None. ASYNC — the composed MCP fleet's
    tools (langchain-mcp-adapters) are async-only, so we drive the graph with `ainvoke` (sync base tools still run,
    LangChain executes them in a threadpool under async)."""
    messages = [("system", load_prompt("operator_system", SYSTEM))]   # B100 P2 — live from the Prompt Registry (fail-safe)
    if history:
        messages += history
    messages.append(("user", message))
    result = await _agent.ainvoke({"messages": messages})
    msgs = result["messages"]
    return msgs[-1].content, _extract_proposal(msgs)
