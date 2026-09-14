# Flow: Realm of Agents — A2A dispatch (B17)

24 corpus-backed specialists in five Norse-named groups behind an A2A surface. Gná routes a task to the best agent;
leads act on their own specialty or delegate to their team and reconcile. The Operator reaches the Realm through a
single `delegate_to_realm` tool. Every agent runs on Claude Haiku (`wl-agentic` LiteLLM lane); every hop is an MLflow trace.

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
    OP->>R: POST /route {message}
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
```

Demo: [demos/realm-of-agents.md](../demos/realm-of-agents.md). Concept: [concepts/realm-of-agents.md](../concepts/realm-of-agents.md).
