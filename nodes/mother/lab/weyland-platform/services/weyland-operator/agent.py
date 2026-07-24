"""The operator agent — a LangGraph ReAct loop over the tool-server tools (B66 Part 1).

Uses LangGraph's prebuilt `create_react_agent` (handles reason → call tool → observe → repeat → answer). The brain is
local **gpt-oss:20b** via Ollama (the B66 bake-off proved it ties Claude Haiku on this exact workload, incl. the
act-path safety test). Read-only for now; act tools + the confirm-step land in Part 3."""
import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from tools import READ_TOOLS

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

SYSTEM = (
    "You are the weyland homelab operator. You operate the lab by calling the available tools, then reply to the user. "
    "Ground every answer in the tool results — never invent lab state. If the knowledge base has nothing on a topic, "
    "say so plainly rather than guessing. Keep replies short and direct (this goes to a Telegram chat)."
)

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)
_agent = create_react_agent(_llm, READ_TOOLS)


def run(message: str, history: list | None = None) -> str:
    """Run the operator on a user message (+ optional prior [(role, text)] turns). Returns the reply text."""
    messages = [("system", SYSTEM)]
    if history:
        messages += history
    messages.append(("user", message))
    result = _agent.invoke({"messages": messages})
    return result["messages"][-1].content
