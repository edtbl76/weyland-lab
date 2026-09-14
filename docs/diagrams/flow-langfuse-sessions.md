# Flow: Langfuse sessions — a run/conversation as one timeline (B103)

Sessions group related traces under one `session_id` so a multi-turn chat, one agent run, or one realm dispatch reads
as a single timeline (combined tokens/cost/duration). Shown: an agent run whose grade + reflect + generate share the
run's `request_id`.

```mermaid
sequenceDiagram
    autonumber
    participant U as Caller
    participant AG as weyland-agent /agent/ask
    participant LF as Langfuse
    U->>AG: POST /agent/ask {query, backend}
    Note over AG: request_id is the session key
    AG->>LF: agent-grade (propagate_attributes session_id=request_id)
    AG->>LF: agent-reflect (same session_id, if it retried)
    AG->>LF: rag-generate (same session_id)
    AG-->>U: answer
    LF->>LF: group traces by session_id into one timeline
    Note over LF: Tracing then Sessions — one row is one interaction (combined tokens/cost/duration)
```

**Read-only.** Other surfaces key by chat_id (operator), request_id (agent), dispatch uuid (realm).
Demo: [demos/langfuse-sessions.md](../demos/langfuse-sessions.md).
