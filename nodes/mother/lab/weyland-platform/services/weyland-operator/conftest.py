"""Test harness for weyland-operator.

The service runs as FLAT modules that import each other by bare name, so put the service dir on ``sys.path``.
``incidents.py`` imports the heavy siblings at module scope — ``agent`` (langgraph/langchain), ``session``
(psycopg2), ``telegram`` (the Telegram SDK) — so we STUB those in ``sys.modules`` here, exposing only the
attributes the imported code references. That keeps the unit tests on the PURE triage logic
(_is_incident / _fingerprint / _who / _investigation_prompt) and the fail-safe prompt cache, with no runtime
deps; the agent/telegram/session paths themselves are exercised live, not here.
"""
import os
import sys
import types

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _stub(name, **attrs):
    """Register a minimal module stub under ``name`` (only if the real one is not already imported)."""
    if name not in sys.modules:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module


async def _noop_run(*_a, **_k):
    return ("", None)


_stub("agent", run=_noop_run)
_stub("session")
_stub("telegram", configured=lambda: False, send_message=_noop_run)
