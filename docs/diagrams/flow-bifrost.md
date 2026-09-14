# Flow: Bifrost — agent MCP edge (B17+B19 / B111)

Bifrost (`bifrost.weyland.lab`) is the coding-agent front door: one `coding-agents` virtual key exposes a 232-tool
MCP surface (the 95-tool read fleet via the FastMCP compositor + external MCPs), a 241-prompt repository, and a
583-skill plugin marketplace — the same VK across Claude Code, Codex, and OpenCode.

```mermaid
sequenceDiagram
    autonumber
    participant A as Coding agent<br/>(Claude Code · Codex · OpenCode)
    participant B as Bifrost<br/>bifrost.weyland.lab
    participant C as Compositor (FastMCP)
    participant F as Read fleet<br/>(6 MCP servers)
    A->>B: POST /mcp (header x-bf-vk = coding-agents VK)
    B->>B: resolve VK to the 232-tool registry
    B->>C: aggregate weyland_fleet (95 tools)
    C->>F: grafana · trino · k8s · postgres · neo4j · datahub (read-only)
    F-->>C: tool results
    C-->>B: aggregated results
    B-->>A: tools/list (232) then tools/call
    Note over A,B: same VK also serves the 241-prompt repo and the 583-skill plugin marketplace (git-served)
```

**Read-only fleet;** write/act tools live on the separate `/mcp-act` mount (Keycloak-authed, `policy.gate`).
Demo: [demos/bifrost.md](../demos/bifrost.md). Runbook: [runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md).
