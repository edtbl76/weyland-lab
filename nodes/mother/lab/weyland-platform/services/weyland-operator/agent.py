"""The operator agent — a LangGraph ReAct loop over the tool-server tools (B66 Part 1).

Uses LangGraph's prebuilt `create_react_agent` (reason → call tool → observe → repeat → answer).

LOCAL-PRIMARY WITH HAIKU FAILOVER (B45 follow-up): the brain is a local model on rogueone ($0). Default qwen2.5:7b —
fast, non-thinking, and it tool-calls cleanly on a SMALL FLAT toolset (proven: one real tool → a clean structured
tool_call in ~2.7s). It gets READ_TOOLS + a CURATED subset of the fleet (LOCAL_FLEET_ALLOW) — deliberately NOT the full
~91 tools and NOT the two-stage router wrappers, both of which broke small-model tool selection (the 91 drown it; the
synthetic router schemas made it emit malformed tool calls). Haiku via LiteLLM is a health FAILOVER only, and gets the
FULL flat fleet (it handles all ~91): a request routes to it when the local engine fails a fast health pre-check or
errors/stalls past the short LOCAL_TIMEOUT — so a rogueone/Ollama outage OR a local fumble degrades to paid cloud
instead of going dark, and steady-state Haiku spend ≈ $0. Set OPERATOR_LLM_FALLBACK=0 for local-only. Both agents are
compiled once at import; `run()` picks local unless it's unavailable."""
import os
import time
from contextlib import contextmanager

import httpx
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from prometheus_client import Counter

from prompts import load_prompt
from tools import ACT_TOOLS, READ_TOOLS
from fleet import load_fleet_tools
from realm import REALM_TOOLS

OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))          # fallback (Haiku) per-call timeout — Haiku is fast
# LOCAL per-call timeout, deliberately SHORT: a warm local call is seconds, so a call dragging past this means the
# engine is stalled or CPU-offloaded (GPU VRAM contended). We want that to TRIP the Haiku failover fast, not hang for
# minutes — the health pre-check catches "down", this catches "up but pathologically slow".
LOCAL_TIMEOUT = float(os.getenv("OPERATOR_LOCAL_TIMEOUT", "60"))


def _bool(v: str) -> bool:
    return str(v).lower() in ("1", "true", "yes")


# PRIMARY — local model on rogueone, direct to Ollama ($0). Default qwen2.5:7b: fast, non-thinking, clean tool-calls.
LOCAL_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
LOCAL_API_KEY = os.getenv("LLM_API_KEY", "ollama")
# A small model tool-calls cleanly only on a FEW real tools. Curate the fleet (namespaced k8s_/grafana_/trino_/…) to the
# ops core for the LOCAL brain. Comma substrings matched against tool names; empty → the full fleet. Anything outside
# this set is still reachable via delegate_to_realm or the Haiku fallback (which always gets the full fleet).
LOCAL_FLEET_ALLOW = [s.strip() for s in os.getenv(
    "LOCAL_FLEET_ALLOW",
    "k8s_pods_list,k8s_pods_get,k8s_pods_log,k8s_events,k8s_nodes_top,k8s_resources_list,"
    "grafana_query_prometheus,grafana_query_loki,trino_execute_query,postgres_execute_sql").split(",") if s.strip()]

# FALLBACK — Haiku via LiteLLM, FULL flat fleet (handles all ~91 tools). Used ONLY when the local engine is unavailable.
FALLBACK_ENABLED = _bool(os.getenv("OPERATOR_LLM_FALLBACK", "1"))
FALLBACK_BASE_URL = os.getenv("OLLAMA_FALLBACK_BASE_URL", "http://litellm.weyland.svc.cluster.local:4000/v1")
FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "claude-haiku")
FALLBACK_API_KEY = os.getenv("OLLAMA_FALLBACK_API_KEY", LOCAL_API_KEY)

# Health pre-check: a cheap liveness GET to the local engine so a down/hung Ollama routes to Haiku in ~seconds instead
# of waiting out OLLAMA_TIMEOUT. Cached briefly so a burst of messages doesn't hammer it.
HEALTH_URL = os.getenv("OLLAMA_HEALTH_URL", "http://192.168.1.230:11434/api/tags")
HEALTH_TIMEOUT = float(os.getenv("OPERATOR_HEALTH_TIMEOUT", "3"))
HEALTH_TTL = float(os.getenv("OPERATOR_HEALTH_TTL", "30"))

SYSTEM = (
    "You are the weyland homelab operator. ALWAYS answer by calling a tool and reporting its result — NEVER tell the "
    "user to run kubectl/SQL/curl themselves; YOU run it. You have read tools for the knowledge base (status, "
    "context_search, context_ask) and for lab subsystems: Kubernetes (pods/namespaces/events), the Trino lakehouse "
    "(SQL/catalogs), Grafana (dashboards/Prometheus), Neo4j (graph), DataHub (catalog/lineage), and Postgres — call the "
    "one that fits and ground your answer in its output. For SPECIALIST work beyond these read tools — engineering, "
    "consulting frameworks, observability/SQL/data-quality/lineage/catalog, research, eval, content — call "
    "delegate_to_realm to hand it to the Realm of Agents (24 experts; Gná routes it) and report their answer. To CHANGE "
    "lab state (trigger a pipeline, run/score evals) you cannot act directly — call propose_act and the user confirms; "
    "never claim an action ran. Keep replies short (Telegram)."
)

# Which brain served each request + why. reason: primary (local ok) | local_down (pre-check miss) | local_error (invoke
# threw). Watch operator_brain_selected_total{brain,reason} — Haiku selections are the failover signal.
_BRAIN_SELECTED = Counter("operator_brain_selected_total", "Operator brain selections by brain + reason",
                          ["brain", "reason"])

_FLEET = load_fleet_tools()   # load the MCP fleet ONCE — Haiku gets all of it; local gets the curated subset below
_LOCAL_FLEET = [t for t in _FLEET if any(a in t.name for a in LOCAL_FLEET_ALLOW)] if LOCAL_FLEET_ALLOW else _FLEET
print(f"[agent] local '{LOCAL_MODEL}' → {len(_LOCAL_FLEET)}/{len(_FLEET)} fleet tools (curated flat: "
      f"{sorted(t.name for t in _LOCAL_FLEET)}); fallback '{FALLBACK_MODEL}' → all {len(_FLEET)}", flush=True)


def _build_agent(base_url: str, model: str, api_key: str, timeout: float, fleet_tools: list):
    """Compile one ReAct agent over READ_TOOLS + the given fleet tools + REALM + ACT. Flat — no router wrappers.
    `timeout` is per-LLM-call: SHORT for local (stall → failover), long for the Haiku fallback."""
    llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model, timeout=timeout, temperature=0)
    return create_react_agent(llm, READ_TOOLS + fleet_tools + REALM_TOOLS + ACT_TOOLS)


_local_agent = _build_agent(LOCAL_BASE_URL, LOCAL_MODEL, LOCAL_API_KEY, LOCAL_TIMEOUT, _LOCAL_FLEET)
_fallback_agent = (_build_agent(FALLBACK_BASE_URL, FALLBACK_MODEL, FALLBACK_API_KEY, OLLAMA_TIMEOUT, _FLEET)
                   if FALLBACK_ENABLED else None)

_health = {"at": 0.0, "ok": True}   # cached liveness of the local engine: (monotonic checked-at, healthy?)


async def _local_healthy() -> bool:
    """Cheap cached liveness for the local engine. Any miss (refused / hung / non-200) → False → route to Haiku fast."""
    now = time.monotonic()
    if now - _health["at"] < HEALTH_TTL:
        return _health["ok"]
    ok = True
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(HEALTH_URL, timeout=HEALTH_TIMEOUT)
            ok = r.status_code == 200
    except Exception:
        ok = False
    _health["at"], _health["ok"] = now, ok
    return ok


def _mark_local_down() -> None:
    """Force the next request to skip the local engine (used when an invoke throws between health checks)."""
    _health["at"], _health["ok"] = time.monotonic(), False


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


# B103 prompt federation — Langfuse prompt-linked tracing (alongside MLflow autolog). Fail-safe.
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
    """B103 — a fail-safe Langfuse generation LINKED to the operator_system prompt version (SDK v4), alongside MLflow.
    Yields a handle (call `.update(output=...)`) or None. Setup/yield separated so a broken SDK call can't double-yield.
    `session_id`/`user_id` group the trace into a Langfuse session (operator: the Telegram chat_id)."""
    if _lf is None:
        yield None
        return
    prop_cm = gen_cm = gen = None
    try:
        prompt = None
        try:
            prompt = _lf.get_prompt(prompt_name, type="chat")
        except Exception:
            pass
        if session_id or user_id:                        # session grouping — propagate_attributes (langfuse v4), set BEFORE the obs
            try:
                from langfuse import propagate_attributes
                prop_cm = propagate_attributes(session_id=session_id, user_id=user_id)
                prop_cm.__enter__()
            except Exception:
                prop_cm = None
        gen_cm = _lf.start_as_current_observation(as_type="generation", name=name, model=model,
                                                  input=input_data, prompt=prompt)
        gen = gen_cm.__enter__()
    except Exception:
        gen_cm = gen = None
    try:
        yield gen
    finally:
        try:
            if gen_cm is not None:
                gen_cm.__exit__(None, None, None)
            if prop_cm is not None:
                prop_cm.__exit__(None, None, None)
            _lf.flush()
        except Exception:
            pass


async def run(message: str, history: list | None = None,
              session_id: str | None = None, user_id: str | None = None) -> tuple[str, dict | None]:
    """Run the operator on a user message (+ optional prior [(role, text)] turns). Returns (reply, proposal). Local is
    primary; on a health-precheck miss or a mid-flight error we re-run the same messages on the Haiku fallback. ASYNC —
    the composed MCP fleet's tools (langchain-mcp-adapters) are async-only, so we drive the graph with `ainvoke`."""
    messages = [("system", load_prompt("operator_system", SYSTEM))]   # B100 P2 — live from the Prompt Registry (fail-safe)
    if history:
        messages += history
    messages.append(("user", message))

    reason = "local_down"   # why we'd use the fallback, if we do
    if _fallback_agent is None or await _local_healthy():
        try:
            with _lf_generation("operator-ask", LOCAL_MODEL, messages, "operator_system", session_id, user_id) as lgen:
                result = await _local_agent.ainvoke({"messages": messages})
                _BRAIN_SELECTED.labels("local", "primary").inc()
                msgs = result["messages"]
                if lgen is not None:
                    lgen.update(output=msgs[-1].content)
                return msgs[-1].content, _extract_proposal(msgs)
        except Exception as exc:
            if _fallback_agent is None:
                raise
            print(f"[agent] local brain failed ({exc}) — falling back to {FALLBACK_MODEL}", flush=True)
            _mark_local_down()
            reason = "local_error"

    with _lf_generation("operator-ask", FALLBACK_MODEL, messages, "operator_system", session_id, user_id) as lgen:
        result = await _fallback_agent.ainvoke({"messages": messages})   # fresh attempt on Haiku (reads are idempotent)
        _BRAIN_SELECTED.labels("haiku", reason).inc()
        msgs = result["messages"]
        if lgen is not None:
            lgen.update(output=msgs[-1].content)
        return msgs[-1].content, _extract_proposal(msgs)
