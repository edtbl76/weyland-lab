# Flow: Realm of Agents — A2A dispatch (B17)

24 corpus-backed specialists in five Norse-named groups behind an A2A surface. Gná routes a task to the best agent;
leads act on their own specialty or delegate to their team and reconcile. The Operator reaches the Realm through a
single `delegate_to_realm` tool, which since B249 (2026-11-19) goes through Bifrost's Agent Gateway (second diagram).
A paid turn runs on Claude Haiku (`wl-agentic` LiteLLM lane); every hop is an MLflow trace.

```mermaid
sequenceDiagram
    autonumber
    participant U as You (Telegram)
    participant OP as Operator (B66)
    participant R as Realm /route (Gná)
    participant L as Realm lead (e.g. Odin)
    participant M as Members (Mímir · Brokkr · …)
    participant G as LiteLLM (Haiku)
    U->>OP: "design & test a semver parser"
    OP->>OP: brain selects delegate_to_realm
    OP->>R: A2A SendMessage (through Bifrost, below)
    R->>R: Gná classifies then picks the best agent
    R->>L: run lead (LangGraph)
    loop each phase / specialty
        L->>M: delegate_to_member (member-as-tool)
        M->>G: think (wl-agentic then Haiku)
        M-->>L: member result
    end
    L->>G: synthesize
    L-->>R: final deliverable
    R-->>OP: {routed_to, role, realm, answer}
    OP-->>U: reply
    Note over R,M: every hop emits an MLflow trace (experiment realm-of-agents)
    Note over R,M: allow_paid false (the default since B209, and the ship transaction) runs every think on the free wl-local lane (qwen2.5:7b-operator on rogueone, LiteLLM fallbacks off) instead of wl-agentic. It was wl-judge until B222 (2026-10-22)
```

## The operator's hop through Bifrost's Agent Gateway (B249)

```mermaid
sequenceDiagram
    autonumber
    participant OP as Operator (delegate_to_realm)
    participant B as Bifrost Agent Gateway
    participant R as Realm /a2a
    participant T as Bifrost MCP (agents-read)
    OP->>B: SendMessage v1, metadata allow_paid true, header x-bf-vk (realm-operator)
    B->>B: is realm granted to this key? (realm-operator only)
    B->>R: SendMessage, header X-Realm-Gateway-Token (from Bifrost's env)
    R->>R: paid only if allow_paid true AND the token matches, else free-only
    R->>T: tool calls, header x-bf-session-id = contextId
    T-->>R: tool results
    R-->>B: message {contextId, parts, metadata routed_to}
    B-->>OP: message
    Note over B,T: Agent Logs record the call (key, contextId), and the MCP logs carry the same session id
    Note over OP,B: no grant gives an error from Bifrost, and the operator does not retry on /route
```

Runbook: [runbooks/realm-of-agents.md](../runbooks/realm-of-agents.md) § Through Bifrost's Agent Gateway.
Decision: [ADR-0015](../adr/0015-adopt-bifrost-agent-gateway-for-the-realm.md).

Demo: [demos/realm-of-agents.md](../demos/realm-of-agents.md). Concept: [concepts/realm-of-agents.md](../concepts/realm-of-agents.md).
