# Flow (E2E) — Operator: Telegram DM → weyland-operator → LiteLLM→Bifrost (Haiku) → MCP / fleet → tool-server → RAG → reply

Cross-system thread grounded in the operator runbook ([../runbooks/operator.md](../runbooks/operator.md))
and [flow-agent-mcp](flow-agent-mcp.md): an inbound Telegram DM drives a **weyland-operator** (B66) turn — the
tool-calling brain is **Haiku** via the `wl-agentic` lane (LiteLLM → Bifrost, a transparent passthrough so tool
schemas survive), and the system-view is the read-only MCP mount on the tool-server (which fans out to the RAG
backends) plus the composed **MCP fleet** (`/mcp-fleet`). Demo: [../demos/operator.md](../demos/operator.md).

```mermaid
sequenceDiagram
    actor U as User (Telegram DM)
    participant OP as weyland-operator<br/>(B66, allowlist + confirm-step)
    participant BR as LiteLLM → Bifrost<br/>(wl-agentic → Haiku)
    participant MCP as tool-server /mcp<br/>(mother :30080, read-only)
    participant FL as MCP fleet /mcp-fleet<br/>(6 read-only servers)
    participant TS as tool-server
    participant RAG as RAG backends<br/>(qdrant / pgvector / weaviate / neo4j)

    U->>OP: DM (allowlisted user)
    OP->>OP: allowlist + guard-in → agent turn
    OP->>BR: ReAct step (wl-agentic → Haiku, tools survive passthrough)
    Note over BR: LiteLLM resolves wl-agentic → Bifrost → Anthropic haiku-4.5<br/>(records cost/tokens/latency, per-VK realm-llm)
    BR-->>OP: decide to call a tool
    alt system-view / RAG (tool-server)
        OP->>MCP: MCP call (status / context_search / context_ask)
        MCP->>TS: invoke tagged route
        TS->>RAG: vector / graph retrieve top-k
        RAG-->>TS: grounded context
        TS-->>MCP: result
        MCP-->>OP: response via MCP
    else platform read (MCP fleet)
        OP->>FL: grafana_* / trino_* / k8s_* / … (read-only)
        FL-->>OP: result
    end
    OP->>BR: synthesize final answer over context
    BR-->>OP: grounded reply
    OP->>OP: guard-out
    OP-->>U: Telegram reply (cites sources)
```

**Seams made explicit:** the operator pod is the front door (Telegram long-poll — no public webhook); the
tool-calling brain runs through the **`wl-agentic`** lane (LiteLLM → Bifrost → Haiku, a transparent passthrough so
tool schemas survive — the MLflow AI Gateway would shred them), while the local Ollama lanes (`wl-rag`/`reason`/
`judge`) stay direct to rogueone; `/mcp` is **read-only** (act tools live on the separate `/mcp-act` mount,
operator-only, fronted by the **live B17+B19 MCP gateway** with a Keycloak-verified actor). The operator can also
**`delegate_to_realm`** — an A2A hand-off to the Realm of Agents (Gná → 24 corpus-backed specialists).
