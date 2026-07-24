"""The operator agent — a LangGraph ReAct loop over the tool-server tools (B66 Part 1).

Uses LangGraph's prebuilt `create_react_agent` (handles reason → call tool → observe → repeat → answer). The brain is
local **gpt-oss:20b** via Ollama (the B66 bake-off proved it ties Claude Haiku on this exact workload, incl. the
act-path safety test). Read-only for now; act tools + the confirm-step land in Part 3."""
import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools import AGENT_TOOLS

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

SYSTEM = (
    "You are the weyland homelab operator. Answer questions by calling the read tools (status, context_search, "
    "context_ask), grounded in their results — never invent lab state, and say so plainly if the knowledge base has "
    "nothing. To CHANGE lab state (trigger a pipeline, run/score evals) you cannot act directly — call propose_act "
    "and the user will be asked to confirm; never claim an action ran. Keep replies short (this goes to Telegram)."
)

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)
_agent = create_react_agent(_llm, AGENT_TOOLS)


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


def run(message: str, history: list | None = None) -> tuple[str, dict | None]:
    """Run the operator on a user message (+ optional prior [(role, text)] turns). Returns (reply, proposal) where
    proposal is a propose_act payload if the agent proposed an action, else None."""
    messages = [("system", SYSTEM)]
    if history:
        messages += history
    messages.append(("user", message))
    result = _agent.invoke({"messages": messages})
    msgs = result["messages"]
    return msgs[-1].content, _extract_proposal(msgs)
