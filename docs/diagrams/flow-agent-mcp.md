# Flow: Agent System-View (Hermes / Claude Code -> MCP -> tool-server)

B2 v1, validated 2026-06-14. The MCP path is read-only (write/act tools gated on B14).

```mermaid
sequenceDiagram
    participant U as User (Telegram DM)
    participant H as Hermes / Claude Code
    participant M as tool-server MCP /mcp
    participant T as tool-server
    participant B as Backends + Ollama
    U->>H: ask system status / search / query
    H->>M: MCP tool call (status / context_search / context_ask / list_models)
    M->>T: invoke route
    T->>B: health checks / vector search / LLM generate
    B-->>T: live state / results
    T-->>H: response via MCP
    H-->>U: grounded answer
```

**Consumers:** Hermes CT 104 (registered in `~/.hermes/config.yaml`) · Claude Code on rogueone (registered via `claude mcp add weyland`).
**Write/act routes** (`/pipeline/trigger`, `/evals/run`, `/evals/score`) are untagged — excluded from MCP v1. Enabled in B14.
