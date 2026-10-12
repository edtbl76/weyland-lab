"""Per-request spend mode (2026-10-12).

Every Realm brain is the Haiku-backed `wl-agentic` lane, which is paid. An automatic caller (the ship-images Realm
transaction) must spend nothing, so it asks for a FREE-ONLY request: inside `free_only()`, `llm.brain()` returns the
free local lane with LiteLLM fallbacks disabled. A ContextVar, not a global: it follows the async call into nested
agents (a lead's delegate_to_* member runs) and ends with the request, so it never leaks into a person's next one.
Pure stdlib, so the app and its tests use the real thing."""
from contextlib import contextmanager
from contextvars import ContextVar

_FREE_ONLY: ContextVar[bool] = ContextVar("realm_free_only", default=False)


def is_free_only() -> bool:
    return _FREE_ONLY.get()


@contextmanager
def free_only():
    token = _FREE_ONLY.set(True)
    try:
        yield
    finally:
        _FREE_ONLY.reset(token)
