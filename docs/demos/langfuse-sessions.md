# Langfuse sessions — a whole conversation/run as one timeline (B103)

A single LLM trace is one call. But the interesting units are bigger: a *multi-turn Telegram chat*, one *agent run*
(grade → reflect → generate), one *realm dispatch* (Gná routes → a specialist runs → it may delegate). **Sessions**
group the related traces under one `session_id` so you read the whole interaction as one timeline — with its combined
tokens, cost, and duration — instead of scattered traces.

## What groups, and by what key

| Surface | Session key | What ends up in one session |
|---|---|---|
| **operator** (Telegram) | the **chat_id** (+ user_id) | every message in that chat |
| **agent** (`/agent/ask`) | a per-run **request_id** | that run's `agent-grade` + `agent-reflect` + `rag-generate` |
| **tool-server** (`/context/ask`) | optional `session_id` (else request_id) | asks sharing a conversation id (e.g. from open-webui) |
| **realm** (`/route`) | a per-dispatch **uuid** | Gná's classify + the chosen agent + any delegated members |

## See it yourself

Both calls go through the meshed `dagster-user-code` pod (so mesh mTLS is handled), on mother:

**Agent** — one run becomes one session (grade + generate, +reflect if it retried):
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import httpx; r=httpx.post('http://weyland-agent.weyland.svc.cluster.local:8080/agent/ask', json={'query':'what does the weyland lab do','backend':'pgvector'}, timeout=600); print(r.status_code, r.text[:400])"
```

**Realm** — Gná's routing + the delegated agent land in one session:
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import httpx; r=httpx.post('http://realm-of-agents.weyland.svc.cluster.local:8080/route', json={'message':'summarize what the weyland lab does and who runs it'}, timeout=180); print(r.status_code, r.text[:400])"
```

**Operator** — just send it a Telegram message; the session keys to your chat.

Then in Langfuse → **Tracing → Sessions**: each row is one interaction. Open the realm one and you'll see two traces
nested — `ChatOpenAI` (Gná's classify → picks an agent) and `LangGraph` (the specialist's ReAct run) — proof the
session id propagated across the delegation.

## How it's wired (two mechanisms)

- **Manual-span apps** (tool-server / operator / agent): the shared `_lf_generation` helper wraps each generation in
  **`propagate_attributes(session_id=…, user_id=…)`** — the langfuse-v4 way to attach trace-level attributes.
- **Realm** (langchain ReAct agents): the langfuse langchain `CallbackHandler` + run config
  `metadata={"langfuse_session_id": <dispatch id>}`, with a **contextvar** carrying the dispatch id through the nested
  delegation so every hop lands in the same session.

> **Gotcha (langfuse 4.x):** there is **no** `Langfuse.update_current_trace` — the trace-attribute API is
> `propagate_attributes(...)`. Calling the non-existent method just raised and got swallowed by the fail-safe wrapper,
> so traces landed with no session. See memory `langfuse-session-tracking`.

Runbook: [runbooks/langfuse.md](../runbooks/langfuse.md) · [runbooks/prompt-federation.md](../runbooks/prompt-federation.md).
