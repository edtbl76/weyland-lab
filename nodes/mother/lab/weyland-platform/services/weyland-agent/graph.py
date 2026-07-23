"""The LangGraph agentic-RAG control loop (B70 Part 3).

    retrieve → grade → { generate | reflect → retrieve }   (bounded by max_attempts)

LangGraph owns the control flow; LlamaIndex retrievers (retrievers.py) do the fetching; a LangChain ChatOpenAI →
Ollama does grade / reflect / generate. Grade and reflect use PROMPT-AND-PARSE (Ollama's OpenAI-compat
function-calling is unreliable across models, so we don't use `.with_structured_output()`). Every LLM + retrieval
step is captured by MLflow's langchain + llama_index autolog → one per-query Trace."""
import os
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from retrievers import VALID_BACKENDS, WeylandRetriever

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))
RETRIEVE_LIMIT = int(os.getenv("AGENT_RETRIEVE_LIMIT", "5"))

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)

RAG_SYSTEM_PROMPT = (
    "You are the Weyland lab assistant. Answer the question using ONLY the context chunks provided. If the context "
    "does not contain the answer, say so plainly rather than guessing. Cite the source name(s) you used."
)


class AgentState(TypedDict):
    query: str              # current (possibly reflected) search query
    original_query: str     # the user's question — graded + answered against this
    backend: str
    chunks: list
    grade: str              # "relevant" | "weak"
    attempts: int
    max_attempts: int
    answer: str
    backend_history: list


def _fmt_context(chunks: list) -> str:
    return "\n\n".join(
        f"[{i + 1}] source: {c['source']} (chunk {c['chunk_index']})\n{c['content']}" for i, c in enumerate(chunks)
    )


def _to_chunk(n) -> dict:
    return {"source": n.node.metadata.get("source", ""), "chunk_index": n.node.metadata.get("chunk_index", 0),
            "similarity": n.score, "content": n.node.get_content()}


def retrieve(state: AgentState) -> dict:
    nodes = WeylandRetriever(state["backend"], limit=RETRIEVE_LIMIT).retrieve(state["query"])
    return {"chunks": [_to_chunk(n) for n in nodes]}


def grade(state: AgentState) -> dict:
    if not state["chunks"]:
        return {"grade": "weak"}
    msg = _llm.invoke(
        f"Question: {state['original_query']}\n\nRetrieved context:\n{_fmt_context(state['chunks'])}\n\n"
        "Does the context contain enough information to answer the question? "
        "Reply with exactly YES or NO on the first line, then one sentence of reason."
    )
    return {"grade": "relevant" if msg.content.strip().upper().startswith("YES") else "weak"}


def reflect(state: AgentState) -> dict:
    others = sorted(VALID_BACKENDS - {state["backend"]})
    msg = _llm.invoke(
        f"The search for the question below returned weak results from the '{state['backend']}' vector backend.\n"
        f"Question: {state['original_query']}\n"
        f"Rewrite the search query to retrieve better chunks, and pick the backend most likely to help "
        f"(current: {state['backend']}; others: {others}).\n"
        "Respond EXACTLY as two lines:\nQUERY: <rewritten query>\nBACKEND: <one backend name>"
    )
    new_query, new_backend = state["query"], state["backend"]
    for line in msg.content.splitlines():
        s = line.strip()
        if s.upper().startswith("QUERY:"):
            new_query = s.split(":", 1)[1].strip() or new_query
        elif s.upper().startswith("BACKEND:"):
            cand = s.split(":", 1)[1].strip().lower()
            if cand in VALID_BACKENDS:
                new_backend = cand
    return {"query": new_query, "backend": new_backend, "attempts": state["attempts"] + 1,
            "backend_history": state["backend_history"] + [new_backend]}


def generate(state: AgentState) -> dict:
    msg = _llm.invoke([
        ("system", RAG_SYSTEM_PROMPT),
        ("user", f"Context:\n{_fmt_context(state['chunks'])}\n\nQuestion: {state['original_query']}"),
    ])
    return {"answer": msg.content}


def _decide(state: AgentState) -> str:
    # answer once the context is good enough OR we've exhausted the retry budget
    if state["grade"] == "relevant" or state["attempts"] >= state["max_attempts"]:
        return "generate"
    return "reflect"


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("reflect", reflect)
    g.add_node("generate", generate)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", _decide, {"generate": "generate", "reflect": "reflect"})
    g.add_edge("reflect", "retrieve")
    g.add_edge("generate", END)
    return g.compile()
