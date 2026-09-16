"""Test harness for realm-of-agents.

The service runs as FLAT modules (config, roster, cards, roles, …) that import each other by bare name
(`from config import ...`), with the service dir on the path — not as a package. So put that dir on
``sys.path`` here and the unit tests import the modules exactly as the running service does.

Scope: these tests cover the PURE-LOGIC modules — the roster (the single-source agent list), the A2A card
builders, and the config/roles data — which need no runtime deps. The framework modules (app.py, a2a.py,
agents.py, stream.py) pull FastAPI + the a2a SDK + httpx and are validated live, not here.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# --- stubs so the framework modules (realms/router/stream) import without their heavy runtime -----------------
# realms/router/stream import langchain/langgraph + the sibling glue modules (agents/fleet/llm/obs/prompts) at
# module scope, but their PURE logic — the delegation-prompt builder, the LangGraph→wire event mapper — needs
# none of it. Stub the heavy libs + those siblings (only the symbols the imports reference), leaving the modules
# under test (realms, router, stream) and the pure data modules (roster, config, cards, roles) REAL.
def _stub(name, **attrs):
    if name not in sys.modules:
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m
    return sys.modules[name]


_stub("langchain_core")
_stub("langchain_core.tools", StructuredTool=type("StructuredTool", (), {}), tool=lambda f=None, **k: (f or (lambda g: g)))
_stub("langgraph")
_stub("langgraph.prebuilt", create_react_agent=lambda *a, **k: None)
_stub("agents", run_solo=lambda *a, **k: None)
_stub("fleet", tools_for=lambda *a, **k: [], tools_for_sync=lambda *a, **k: [])
_stub("llm", brain=lambda *a, **k: None)
_stub("obs", lf_config=lambda *a, **k: {}, log=lambda *a, **k: None, set_session=lambda *a, **k: None)
_stub("prompts", load_role=lambda spec: f"[role:{getattr(spec, 'key', '?')}]", load_prompt=lambda *a, **k: "")
