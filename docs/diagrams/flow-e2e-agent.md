# Flow (E2E) — Agent: Telegram DM → Hermes → LiteLLM plan / Ollama → MCP → tool-server → RAG → reply

Cross-system thread grounded in the Hermes runbook ([../runbooks/agent-hermes.md](../runbooks/agent-hermes.md))
and [flow-agent-mcp](flow-agent-mcp.md): an inbound Telegram DM drives a Hermes agent turn — planning aux lanes
hit the LiteLLM model-gateway (Gemini free), the default brain is local `qwen3-coder` on Ollama (rogueone), and
the system-view is the read-only MCP mount on the tool-server, which fans out to the RAG backends. Demo:
[../demos/agent-e2e.md](../demos/agent-e2e.md).

```mermaid
sequenceDiagram
    actor U as User (Telegram DM)
    participant GW as hermes-gateway<br/>(CT 104, allowlist)
    participant LLM as LiteLLM model-gateway<br/>(:30400, planning aux — Gemini free)
    participant OLL as Ollama<br/>(rogueone :11434, qwen3-coder:30b)
    participant MCP as tool-server /mcp<br/>(mother :30080, read-only)
    participant TS as tool-server
    participant RAG as RAG backends<br/>(qdrant / pgvector / weaviate / neo4j)

    U->>GW: DM (allowlisted user)
    GW->>GW: allowlist check → agent turn
    opt planning (decompose / specify)
        GW->>LLM: plan step (gemini-flash via model-gateway)
        LLM-->>GW: plan
    end
    GW->>OLL: chat completion (default brain, reason→act loop)
    OLL-->>GW: decide to call a tool (tool_search)
    GW->>MCP: MCP call (status / context_search / context_ask)
    MCP->>TS: invoke tagged route
    TS->>RAG: vector / graph retrieve top-k
    RAG-->>TS: grounded context
    TS-->>MCP: result
    MCP-->>GW: response via MCP
    GW->>OLL: synthesize final answer over context
    OLL-->>GW: grounded reply
    GW-->>U: Telegram reply (cites sources)
```

**Seams made explicit:** the gateway is the front door (headless systemd, polling — no public webhook); the
planning aux lanes are pinned to the LiteLLM model-gateway while the executing brain stays local Ollama; `/mcp` is
**read-only** (act tools live on the separate `/mcp-act` mount, Hermes-only). First turn after a (re)start
cold-prefills the ~17K base prompt (~3.5 min); warm turns are ~6-17 s.
