"""The LangGraph agentic-RAG control loop (B70 Part 3).

    retrieve → grade → { generate | reflect → retrieve }   (bounded by max_attempts)

LangGraph owns the control flow; LlamaIndex retrievers (retrievers.py) do the fetching; a LangChain ChatOpenAI →
Ollama does grade / reflect / generate. Grade and reflect use PROMPT-AND-PARSE (Ollama's OpenAI-compat
function-calling is unreliable across models, so we don't use `.with_structured_output()`). Every LLM + retrieval
step is captured by MLflow's langchain + llama_index autolog → one per-query Trace."""
import os
from contextlib import contextmanager
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from prompts import load_prompt, render_prompt
from retrievers import VALID_BACKENDS, WeylandRetriever

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))
RETRIEVE_LIMIT = int(os.getenv("AGENT_RETRIEVE_LIMIT", "5"))

_llm = ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL,
                  timeout=OLLAMA_TIMEOUT, temperature=0)

# B103 prompt federation — Langfuse prompt-linked tracing (alongside MLflow autolog). Fail-safe: never blocks a step.
_lf = None
if os.getenv("LANGFUSE_PUBLIC_KEY"):
    try:
        from langfuse import Langfuse
        _lf = Langfuse()   # reads LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
        print("[langfuse] prompt-linked tracing enabled", flush=True)
    except Exception as _exc:
        print(f"[langfuse] tracing disabled: {_exc}", flush=True)


@contextmanager
def _lf_generation(name: str, model: str, input_data, prompt_name: str,
                   session_id: str | None = None, user_id: str | None = None):
    """B103 — a fail-safe Langfuse generation LINKED to the Langfuse prompt version (SDK v4), alongside MLflow. Yields a
    handle (call `.update(output=...)`) or None if Langfuse is off/broken. Setup and yield are separated so a broken
    SDK call can't double-yield; flushes on exit. `session_id` groups the run's grade/reflect/generate into one session."""
    if _lf is None:
        yield None
        return
    gen_cm = gen = None
    try:
        prompt = None
        try:
            prompt = _lf.get_prompt(prompt_name, type="chat")   # object carries the version -> links the trace
        except Exception:
            pass
        gen_cm = _lf.start_as_current_observation(as_type="generation", name=name, model=model,
                                                  input=input_data, prompt=prompt)
        gen = gen_cm.__enter__()
        if session_id or user_id:                        # session grouping — all 3 calls of one /agent/ask run
            try:
                _lf.update_current_trace(session_id=session_id, user_id=user_id)
            except Exception:
                pass
    except Exception:
        gen_cm = gen = None
    try:
        yield gen
    finally:
        try:
            if gen_cm is not None:
                gen_cm.__exit__(None, None, None)
            _lf.flush()
        except Exception:
            pass

RAG_SYSTEM_PROMPT = (
    "You are the Weyland lab assistant. Answer the question using ONLY the context chunks provided. If the context "
    "does not contain the answer, say so plainly rather than guessing. Cite the source name(s) you used."
)
# B100 P2 — templated fallbacks (must match the registered `agent_grade` / `agent_reflect` templates); the live
# versions come from the Prompt Registry via render_prompt.
_GRADE_PROMPT = (
    "Question: {question}\n\nRetrieved context:\n{context}\n\nDoes the context contain enough information to "
    "answer the question? Reply with exactly YES or NO on the first line, then one sentence of reason."
)
_REFLECT_PROMPT = (
    "The search for the question below returned weak results from the '{backend}' vector backend.\n"
    "Question: {question}\n"
    "Rewrite the search query to retrieve better chunks, and pick the backend most likely to help "
    "(current: {backend}; others: {others}).\n"
    "Respond EXACTLY as two lines:\nQUERY: <rewritten query>\nBACKEND: <one backend name>"
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
    session_id: str        # per-run id → groups grade/reflect/generate into one Langfuse session


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
    _p = render_prompt("agent_grade", _GRADE_PROMPT,
                       question=state["original_query"], context=_fmt_context(state["chunks"]))
    with _lf_generation("agent-grade", OLLAMA_MODEL, _p, "agent_grade", state.get("session_id")) as lgen:
        msg = _llm.invoke(_p)
        if lgen is not None:
            lgen.update(output=msg.content)
    return {"grade": "relevant" if msg.content.strip().upper().startswith("YES") else "weak"}


def reflect(state: AgentState) -> dict:
    others = sorted(VALID_BACKENDS - {state["backend"]})
    _p = render_prompt("agent_reflect", _REFLECT_PROMPT,
                       backend=state["backend"], question=state["original_query"], others=others)
    with _lf_generation("agent-reflect", OLLAMA_MODEL, _p, "agent_reflect", state.get("session_id")) as lgen:
        msg = _llm.invoke(_p)
        if lgen is not None:
            lgen.update(output=msg.content)
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
    _msgs = [
        ("system", load_prompt("rag_system", RAG_SYSTEM_PROMPT)),
        ("user", f"Context:\n{_fmt_context(state['chunks'])}\n\nQuestion: {state['original_query']}"),
    ]
    with _lf_generation("rag-generate", OLLAMA_MODEL, _msgs, "rag_system", state.get("session_id")) as lgen:
        msg = _llm.invoke(_msgs)
        if lgen is not None:
            lgen.update(output=msg.content)
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
