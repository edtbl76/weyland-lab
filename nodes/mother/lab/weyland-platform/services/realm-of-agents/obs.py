"""Live step logging → stdout, so `kubectl logs -f deploy/realm-of-agents` shows the delegation moving in real time.

Until the streaming UI exists, this is how you 'hear the bytes move': every routing decision, every delegation, and
every agent's start/finish prints the moment it happens (flushed). Run the request in one pane and tail logs in another."""
import contextvars
import os
import sys


def log(msg: str) -> None:
    print(f"[realm] {msg}", flush=True, file=sys.stdout)


# --- Langfuse session tracing (fail-safe) -----------------------------------------------------------------------------
# One dispatch = one Langfuse session. The session id is held in a contextvar set at the dispatch entry, so it
# propagates through the async delegation chain (lead → delegate_to_* → member run_solo run in the SAME task) without
# threading it through every signature. `lf_config` merges the langchain CallbackHandler + session metadata into each
# graph's run config; a broken/absent Langfuse never changes behaviour (returns the base config unchanged).
_session: contextvars.ContextVar[str | None] = contextvars.ContextVar("lf_session", default=None)

_lf_handler = None
try:
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        from langfuse.langchain import CallbackHandler
        _lf_handler = CallbackHandler()
except Exception as _exc:   # noqa: BLE001 — tracing must never break dispatch
    print(f"[realm] langfuse tracing disabled: {_exc}", flush=True)
    _lf_handler = None


def set_session(session_id: str) -> None:
    """Set the current dispatch's Langfuse session id (propagates via contextvar through the whole delegation tree)."""
    _session.set(session_id)


def lf_config(base: dict | None = None) -> dict:
    """Merge the Langfuse callback + `langfuse_session_id` metadata into a LangChain run config. Fail-safe: with
    Langfuse off, returns `base` unchanged, so every ainvoke/astream_events call site is a no-op drop-in."""
    cfg = dict(base or {})
    if _lf_handler is None:
        return cfg
    cfg["callbacks"] = [*cfg.get("callbacks", []), _lf_handler]
    md = dict(cfg.get("metadata") or {})
    sid = _session.get()
    if sid:
        md["langfuse_session_id"] = sid
    cfg["metadata"] = md
    return cfg
