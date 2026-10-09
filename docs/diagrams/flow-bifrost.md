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

## Who authenticates how (v2.2.6, B202 — 2026-10-09)

```mermaid
sequenceDiagram
    autonumber
    participant L as LiteLLM (hosted lanes)
    participant R as Register scripts · Dagster registrations · Realm
    participant P as Prometheus
    participant B as Bifrost v2.2.6
    L->>B: POST /v1/chat/completions (x-bf-vk = realm-llm)
    B->>B: enforce_auth_on_inference - a virtual key is required
    B-->>L: 200 (no key - 401)
    R->>B: GET or POST /api/... (X-Bifrost-Setup-Token)
    B->>B: setup lock (dashboard auth off) - token checked
    B-->>R: 200 (none - 401, wrong - 403)
    P->>B: GET /metrics
    B->>B: client_config.whitelisted_routes includes /metrics
    B-->>P: 200 (bifrost_cost_total for BifrostSpendObserved)
```

The three settings live in `config.db` and are restored by `register_bifrost_client_config.py`; the token is the sealed
`bifrost-setup-token` Secret (runbook § Bifrost setup token).

**Read-only fleet;** write/act tools live on the separate `/mcp-act` mount (Keycloak-authed, `policy.gate`).
Demo: [demos/bifrost.md](../demos/bifrost.md). Runbook: [runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md).
