"""Test harness for weyland-agent (first tests, B255, 2026-11-20).

graph.py imports LangChain, LangGraph, the LlamaIndex retrievers and the prompt registry at module scope and compiles
its graph at import. These tests cover the node logic only, so the heavy modules are stubbed by name before graph.py
is imported; the service dir is put on sys.path the way the running service sees it.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _stub(name, **attrs):
    m = sys.modules.get(name) or types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _Graph:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, _name):
        return lambda *a, **k: self


class _LLM:
    def __init__(self, *a, **k):
        pass

    def invoke(self, messages):
        return types.SimpleNamespace(content="an answer")


_stub("langchain_openai", ChatOpenAI=_LLM)
_stub("langgraph")
_stub("langgraph.graph", END="END", StateGraph=_Graph)
_stub("retrievers", VALID_BACKENDS=("pgvector",), WeylandRetriever=lambda *a, **k: None)
_stub("prompts", load_prompt=lambda name, default="": default, render_prompt=lambda *a, **k: "")
