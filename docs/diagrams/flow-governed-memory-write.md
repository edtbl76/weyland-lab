# Flow: a governed write to the shared memory (B256)

A person (through Open WebUI) or an agent (with its own Keycloak client) writes to the shared memory through the
governed gateway. The gateway sets the caller's identity from the validated token; the memory compositor decides, stamps
provenance and forwards to Basic Memory. Design: [shared-context-design.md](../design/shared-context-design.md);
runbook: [shared-agent-memory.md](../runbooks/shared-agent-memory.md); decision: [ADR-0019](../adr/0019-shared-context-layers-with-governed-writes.md).

```mermaid
sequenceDiagram
    participant C as Caller (person via Open WebUI, or an agent client)
    participant K as Keycloak
    participant G as weyland-mcp-gateway (/mcp-memory)
    participant M as memory compositor (GOVERNED_WRITE=1)
    participant B as Basic Memory (rogueone :8765)
    C->>K: token (the person's own, or client_credentials)
    C->>G: governed_write_note + Bearer token
    G->>G: validate JWT, strip client-sent identity headers
    G->>M: X-Forwarded-User (person) and X-Forwarded-Consumer (client)
    M->>M: rights table for this identity and layer, path and title check, secret check
    alt refused
        M-->>C: tool error naming the rule (and one mcp-memory-write audit line)
    else allowed
        M->>B: read_content (does the note exist, which version)
        M->>B: write_note or edit_note with provenance metadata
        B-->>M: written
        M-->>C: created, appended or replaced (and one audit line)
    end
```
