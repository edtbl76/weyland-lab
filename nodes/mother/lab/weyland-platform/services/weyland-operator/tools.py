"""Operator tools — LangChain tools wrapping the tool-server's READ endpoints (B66 Part 1).

The operator reasons over the SAME `/mcp` read plane the agent + Claude Code use, via HTTP. Each tool's docstring is
the description gpt-oss's native tool-calling reads, and the type-hinted args become the schema. Failures return an
error string (never raise) so the agent can react rather than crash. ACT tools (pipeline_trigger, evals_*) are added
in Part 3 as PROPOSE-only — they are deliberately absent here."""
import os

import httpx
from langchain_core.tools import tool

TOOLSERVER = os.getenv("TOOLSERVER", "http://weyland-tool-server.weyland.svc.cluster.local:8080")
ASK_TIMEOUT = float(os.getenv("TOOL_ASK_TIMEOUT", "300"))  # context_ask calls the tool-server's LLM → slow


@tool
def status() -> str:
    """Get the consolidated health of the weyland lab: server, embedding model, LLM endpoint, and all four vector
    backends (pgvector, qdrant, weaviate, neo4j). Use this for 'is the lab healthy / is X up' questions. No arguments."""
    try:
        return httpx.get(f"{TOOLSERVER}/status", timeout=30).text
    except Exception as e:
        return f'{{"error": "status failed: {e}"}}'


@tool
def context_search(query: str, backend: str = "pgvector") -> str:
    """Retrieve raw knowledge-base chunks (no answer generation) for a query. backend is one of
    pgvector|qdrant|weaviate|neo4j (default pgvector). Use when you want the source chunks, not a synthesized answer."""
    try:
        return httpx.post(f"{TOOLSERVER}/context/search", params={"backend": backend},
                          json={"query": query, "limit": 3}, timeout=60).text
    except Exception as e:
        return f'{{"error": "context_search failed: {e}"}}'


@tool
def context_ask(query: str, backend: str = "pgvector") -> str:
    """Answer a question from the knowledge base using RAG (retrieve + generate an answer). backend defaults to
    pgvector. Use this for 'what does the docs/KB say about X' questions. Slower (it generates an answer)."""
    try:
        return httpx.post(f"{TOOLSERVER}/context/ask",
                          json={"query": query, "backend": backend}, timeout=ASK_TIMEOUT).text
    except Exception as e:
        return f'{{"error": "context_ask failed: {e}"}}'


READ_TOOLS = [status, context_search, context_ask]
