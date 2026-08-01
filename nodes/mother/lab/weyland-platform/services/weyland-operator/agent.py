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
from realm import REALM_TOOLS

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

SYSTEM = (
    "You are the weyland homelab operator. ALWAYS answer by calling a tool and reporting its result — NEVER tell the "
    "user to run kubectl/SQL/curl themselves; YOU run it. You have read tools for the knowledge base (status, "
    "context_search, context_ask) and for lab subsystems: Kubernetes (pods/namespaces/events), the Trino lakehouse "
    "(SQL/catalogs), Grafana (dashboards/Prometheus), Neo4j (graph), DataHub (catalog/lineage), and Postgres — call the "
    "one that fits and ground your answer in its output. For SPECIALIST work beyond these read tools — engineering, "
    "consulting frameworks, observability/SQL/data-quality/lineage/catalog, research, eval, content — call "
    "delegate_to_realm to hand it to the Realm of Agents (24 experts; Gná routes it) and report their answer. To CHANGE "
    "lab state (trigger a pipeline, run/score evals) you cannot act directly — call propose_act and the user confirms; "
    "never claim an action ran. Keep replies short (Telegram)."
)

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key=os.getenv("LLM_API_KEY", "ollama"), model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)
# Fleet tools: FLAT by default — a capable brain (Haiku) selects from the ~91 read tools directly. Set FLEET_ROUTING=1
# for the local gpt-oss:20b, which collapses the fleet into 6 subsystem ROUTERS (small prompts, extra LLM hops) so it
# stays within the 20B's tool-selection ceiling. Empty either way if the fleet is unreachable.
_FLEET = load_fleet_tools()
_fleet_tools = build_router_tools(_FLEET, _llm) if os.getenv("FLEET_ROUTING") else _FLEET
_agent = create_react_agent(_llm, READ_TOOLS + _fleet_tools + REALM_TOOLS + ACT_TOOLS)


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
