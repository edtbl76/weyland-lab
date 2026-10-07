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
import asyncio
import os
import time
from contextlib import contextmanager

import httpx
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from prometheus_client import Counter

import decide
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


# PRIMARY — local model on rogueone, direct to Ollama ($0). qwen2.5:7b (fast, non-thinking, clean tool-calls) built as
# `qwen2.5:7b-operator` with a 32K window (nodes/rogueone/ollama/qwen2.5-7b-operator.Modelfile). The stock tag ran with
# ~2K per request and Ollama silently cut the ~6K-token prompt — the cause of the 2026-10-03 empty replies.
LOCAL_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-operator")
# Cap each tool result the LOCAL brain sees (chars, ~4/token). One `k8s_pods_list_in_namespace` is ~18K tokens — on its
# own more than a 16K slot. The graph keeps the full result; only the model's input is trimmed. Haiku is not capped.
LOCAL_TOOL_RESULT_CAP = int(os.getenv("LOCAL_TOOL_RESULT_CAP", "12000"))
LOCAL_API_KEY = os.getenv("LLM_API_KEY", "ollama")
# A small model tool-calls cleanly only on a FEW real tools. Curate the fleet (namespaced k8s_/grafana_/trino_/…) to the
# ops core for the LOCAL brain. Comma substrings matched against tool names; empty → the full fleet. Anything outside
# this set is still reachable via delegate_to_realm or the Haiku fallback (which always gets the full fleet).
LOCAL_FLEET_ALLOW = [s.strip() for s in os.getenv(
    "LOCAL_FLEET_ALLOW",
    "k8s_pods_list,k8s_pods_get,k8s_pods_log,k8s_events,k8s_nodes_top,k8s_resources_list,"
    "grafana_query_prometheus,grafana_query_loki,trino_execute_query,postgres_execute_sql,"
    # B182 (2026-10-03): recall from the shared agent memory — the compositor fleet exposes its read tools as memory_*
    "memory_search_notes,memory_read_note").split(",") if s.strip()]

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
    "never claim an action ran. For what the team has decided, learned or recorded before (lessons, past incidents, why "
    "something is set up the way it is), search the shared agent memory with memory_search_notes, then open the best "
    "match with memory_read_note and answer from that note. Keep replies short (Telegram)."
)

# Which brain served each request + why. reason: primary (local ok) | local_down (pre-check miss) | local_error (invoke
# threw) | local_empty (answered with no text — EmptyReply). Watch operator_brain_selected_total{brain,reason} — Haiku
# selections are the failover signal; brain="none" is a no-fallback caller (the incident sweep) that did not pay.
_BRAIN_SELECTED = Counter("operator_brain_selected_total", "Operator brain selections by brain + reason",
                          ["brain", "reason"])

FLEET_RETRY_INTERVAL = float(os.getenv("OPERATOR_FLEET_RETRY", "30"))   # seconds between fleet-load attempts


def _cap_tool_results(state: dict) -> dict:
    """LangGraph pre_model_hook for the LOCAL brains: trim any tool result over LOCAL_TOOL_RESULT_CAP before the model
    sees it, with a note saying how much was cut. Returned as `llm_input_messages`, so the graph state keeps the full
    result. Duck-typed (`type == "tool"`, `model_copy`) so the slim test lane needs no langchain."""
    out = []
    for m in state["messages"]:
        if getattr(m, "type", None) == "tool":
            text = _text(m.content)
            if len(text) > LOCAL_TOOL_RESULT_CAP:
                more = len(text) - LOCAL_TOOL_RESULT_CAP
                m = m.model_copy(update={"content": f"{text[:LOCAL_TOOL_RESULT_CAP]}\n[... truncated {more} more "
                                                    f"characters — narrow the query (namespace, labelSelector, a "
                                                    f"shorter time range) if the answer needs them]"})
        out.append(m)
    return {"llm_input_messages": out}


def _build_agent(base_url: str, model: str, api_key: str, timeout: float, fleet_tools: list, realm: bool = True,
                 cap: bool = False):
    """Compile one ReAct agent over READ_TOOLS + the given fleet tools + REALM + ACT. Flat — no router wrappers.
    `timeout` is per-LLM-call: SHORT for local (stall → failover), long for the Haiku fallback. `realm=False` leaves
    out delegate_to_realm — the Realm runs on the PAID wl-agentic Haiku lane whichever brain calls it."""
    llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model, timeout=timeout, temperature=0)
    tools = READ_TOOLS + fleet_tools + (REALM_TOOLS if realm else []) + ACT_TOOLS
    if cap:   # `cap` = a small-window local brain; see _cap_tool_results
        return create_react_agent(llm, tools, pre_model_hook=_cap_tool_results)
    return create_react_agent(llm, tools)


def _install_fleet(fleet: list) -> None:
    """(Re)compile the brains over `fleet` — Haiku gets all of it; local gets the curated subset; the UNPAID brain is
    the local one without delegate_to_realm (what allow_fallback=False runs on — it can spend nothing). Swapping the
    module globals is safe mid-request: run() reads them once per call."""
    global _local_agent, _fallback_agent, _unpaid_agent, _unpaid_tools
    local = [t for t in fleet if any(a in t.name for a in LOCAL_FLEET_ALLOW)] if LOCAL_FLEET_ALLOW else fleet
    _unpaid_tools = READ_TOOLS + local + ACT_TOOLS   # what a sweep's brain can call (no Realm) — B174 shadow options
    _local_agent = _build_agent(LOCAL_BASE_URL, LOCAL_MODEL, LOCAL_API_KEY, LOCAL_TIMEOUT, local, cap=True)
    _unpaid_agent = _build_agent(LOCAL_BASE_URL, LOCAL_MODEL, LOCAL_API_KEY, LOCAL_TIMEOUT, local, realm=False, cap=True)
    _fallback_agent = (_build_agent(FALLBACK_BASE_URL, FALLBACK_MODEL, FALLBACK_API_KEY, OLLAMA_TIMEOUT, fleet)
                       if FALLBACK_ENABLED else None)
    print(f"[agent] local '{LOCAL_MODEL}' → {len(local)}/{len(fleet)} fleet tools (curated flat: "
          f"{sorted(t.name for t in local)}); fallback '{FALLBACK_MODEL}' → all {len(fleet)}", flush=True)


# Load the MCP fleet at import. None = a secret is wired but the load failed (Keycloak/gateway not up yet, e.g. right
# after a node stall): start with no fleet, report NOT Ready (app /ready), and let fleet_retry_loop keep trying.
_first_fleet = load_fleet_tools()
_fleet = {"loaded": _first_fleet is not None}
_install_fleet(_first_fleet or [])


def sweep_tools() -> list[tuple[str, str]]:
    """(name, description) of every tool the sweep's unpaid brain can call — the options the B174 shadow chooses from."""
    return [(t.name, t.description or "") for t in _unpaid_tools]


def sweep_rules() -> str:
    """The system prompt the sweep's brain runs under (live from the Prompt Registry, fail-safe to SYSTEM)."""
    return load_prompt("operator_system", SYSTEM)


def fleet_ready() -> bool:
    """True once the fleet has loaded (or no secret is wired, so there is none to load). Gates the /ready probe."""
    return _fleet["loaded"]


async def fleet_retry_loop(interval: float = FLEET_RETRY_INTERVAL) -> None:
    """Retry the fleet load until it succeeds, then rebuild both brains with it. Returns at once if already loaded.
    load_fleet_tools blocks (asyncio.run inside), so each attempt runs in a worker thread."""
    if _fleet["loaded"]:
        return
    while True:   # a timed retry of a failing external call — not waiting on in-process state, so not an Event
        await asyncio.sleep(interval)
        fleet = await asyncio.to_thread(load_fleet_tools)
        if fleet is not None:
            _install_fleet(fleet)
            _fleet["loaded"] = True
            print(f"[fleet] loaded on retry — {len(fleet)} tools; operator Ready", flush=True)
            return

_health = {"at": 0.0, "ok": True}   # cached liveness of the local engine: (monotonic checked-at, healthy?)


class LocalUnavailable(Exception):
    """The local brain is down or failed, and the caller said not to spend money (`allow_fallback=False`).
    The incident sweep uses this to defer and retry later instead of paying (2026-10-02: during eval runs, sweeps on
    Haiku — which then delegated to the Realm, itself on paid Haiku — cost $12.44 in 14 days on a $0 budget)."""


class EmptyReply(Exception):
    """A brain finished with no text and proposed nothing — a failure, never an answer. Found live 2026-10-03: after
    any fleet tool call qwen2.5:7b's final turn came back from Ollama as `{"content": ""}` (finish=stop, tokens spent,
    no tool call); with no exception there was no failover, so the person got a blank reply counted as a success."""


def _text(content) -> str:
    """The reply's text, whether the model returned a string or a list of content blocks."""
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return content or ""


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
              session_id: str | None = None, user_id: str | None = None,
              allow_fallback: bool = True, trace: dict | None = None) -> tuple[str, dict | None]:
    """Run the operator on a user message (+ optional prior [(role, text)] turns). Returns (reply, proposal). Local is
    primary; on a health-precheck miss or a mid-flight error we re-run the same messages on the Haiku fallback. ASYNC —
    the composed MCP fleet's tools (langchain-mcp-adapters) are async-only, so we drive the graph with `ainvoke`.
    `allow_fallback=False` (automatic callers — the incident sweep) can spend NOTHING: it runs on the unpaid local brain
    (no delegate_to_realm — the Realm is on paid Haiku), and a down or failing local brain raises LocalUnavailable
    instead of failing over to Haiku. A person chatting keeps both so the operator still answers them.
    `trace`, if given, gets `first_tool` — the first tool the answering brain called (B174 shadow baseline)."""
    messages = [("system", load_prompt("operator_system", SYSTEM))]   # B100 P2 — live from the Prompt Registry (fail-safe)
    if history:
        messages += history
    messages.append(("user", message))

    if not allow_fallback:
        return await _run_local_only(messages, session_id, user_id, trace)

    reason = "local_down"   # why we'd use the fallback, if we do
    if _fallback_agent is None or await _local_healthy():
        try:
            return await _invoke(_local_agent, LOCAL_MODEL, "local", "primary", messages, session_id, user_id, trace)
        except EmptyReply as exc:
            if _fallback_agent is None:
                raise
            # the engine answered — its output was bad. Fail over THIS request; keep local primary for the next one.
            print(f"[agent] {exc} — falling back to {FALLBACK_MODEL}", flush=True)
            reason = "local_empty"
        except Exception as exc:
            if _fallback_agent is None:
                raise
            print(f"[agent] local brain failed ({exc}) — falling back to {FALLBACK_MODEL}", flush=True)
            _mark_local_down()
            reason = "local_error"
    # fresh attempt on Haiku (reads are idempotent)
    return await _invoke(_fallback_agent, FALLBACK_MODEL, "haiku", reason, messages, session_id, user_id, trace)


async def _invoke(brain_agent, model: str, brain: str, reason: str, messages: list,
                  session_id: str | None, user_id: str | None, trace: dict | None = None) -> tuple[str, dict | None]:
    """One traced invoke of `brain_agent`; counts the selection only when it answered. No text and no proposal is
    EmptyReply — an answer that says nothing is not an answer (a proposal alone is: the app shows its confirm step)."""
    with _lf_generation("operator-ask", model, messages, "operator_system", session_id, user_id) as lgen:
        result = await brain_agent.ainvoke({"messages": messages})
        msgs = result["messages"]
        if trace is not None:
            trace["first_tool"] = decide.first_tool_called(msgs)
        if lgen is not None:
            lgen.update(output=msgs[-1].content)
        proposal = _extract_proposal(msgs)
        if not _text(msgs[-1].content).strip() and proposal is None:
            raise EmptyReply(f"{model} returned an empty reply")
        _BRAIN_SELECTED.labels(brain, reason).inc()
        return msgs[-1].content, proposal


async def _run_local_only(messages: list, session_id: str | None, user_id: str | None,
                          trace: dict | None = None) -> tuple[str, dict | None]:
    """The no-fallback path (allow_fallback=False): the unpaid local brain or LocalUnavailable — never paid Haiku, never
    the Realm."""
    if not await _local_healthy():
        _BRAIN_SELECTED.labels("none", "local_down").inc()
        raise LocalUnavailable(f"local brain {LOCAL_MODEL} failed its health pre-check")
    try:
        return await _invoke(_unpaid_agent, LOCAL_MODEL, "local", "primary", messages, session_id, user_id, trace)
    except EmptyReply:
        # healthy engine, bad output: not marked down, and NOT LocalUnavailable — that defers the sweep to retry, and
        # this failure is persistent, so the incident would never post. The sweep posts it with the reason instead.
        _BRAIN_SELECTED.labels("none", "local_empty").inc()
        raise
    except Exception as exc:
        _mark_local_down()
        _BRAIN_SELECTED.labels("none", "local_error").inc()
        raise LocalUnavailable(f"local brain {LOCAL_MODEL} failed: {exc}") from exc
