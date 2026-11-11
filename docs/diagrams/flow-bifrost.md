# Flow: Bifrost — agent MCP edge (B17+B19 / B111)

Bifrost (`bifrost.weyland.lab`) is the coding-agent front door: one `coding-agents` virtual key exposes the
MCP surface (the read fleet via the FastMCP compositor + external MCPs), the prompt repository, and the
skill plugin marketplace (live counts: the nightly `bifrost-backup` log line, `runbooks/mcp-gateway.md`) — the same VK across Claude Code, Codex, and OpenCode.

```mermaid
sequenceDiagram
    autonumber
    participant A as Coding agent<br/>(Claude Code · Codex · OpenCode)
    participant B as Bifrost<br/>bifrost.weyland.lab
    participant C as Compositor (FastMCP)
    participant F as Read fleet<br/>(6 MCP servers)
    A->>B: POST /mcp (header x-bf-vk = coding-agents VK)
    B->>B: resolve VK to its granted tools (299 on 2026-11-11)
    B->>C: aggregate weyland_fleet (95 tools)
    C->>F: grafana · trino · k8s · postgres · neo4j · datahub (read-only)
    F-->>C: tool results
    C-->>B: aggregated results
    B-->>A: tools/list (299) then tools/call
    Note over A,B: same VK also serves the prompt repo and the skill plugin marketplace (git-served)
```

## Who authenticates how (since v2.2.6, B202 — 2026-10-09; unchanged on v2.3.1, B231)

```mermaid
sequenceDiagram
    autonumber
    participant L as LiteLLM (hosted lanes)
    participant R as Register scripts · Dagster registrations · Realm
    participant P as Prometheus
    participant B as Bifrost v2.3.1
    L->>B: POST /v1/chat/completions (x-bf-vk = realm-llm)
    B->>B: enforce_auth_on_inference - a virtual key is required
    B-->>L: 200 (no key - 401)
    R->>B: GET or POST /api/... (X-Bifrost-Setup-Token)
    B->>B: setup lock (dashboard auth off) - token checked
    B-->>R: 200 (none - 401, wrong - 403)
    P->>B: GET /metrics
    B->>B: client_config.whitelisted_routes includes /metrics
    B-->>P: 200 (bifrost_cost_total for BifrostSpendObserved)
    R->>B: PUT /api/governance/virtual-keys/ID mcp_configs (register_bifrost_vk_mcp.py, B203)
    B->>B: resolve clients by name, reload the key in memory - no restart
    participant W as bifrost-mcp-watchdog (daily 03:50)
    participant AM as Alertmanager to Telegram
    W->>B: GET /api/mcp/clients (X-Bifrost-Setup-Token)
    B-->>W: every client with its state
    W->>AM: BifrostMCPClientUnhealthy per client not healthy
```

## An OAuth MCP client (Jam, Linear, Hugging Face) — dynamic client registration (B192, 2026-11-11)

```mermaid
sequenceDiagram
    autonumber
    participant R as register_bifrost_mcp_clients.py (in-cluster)
    participant B as Bifrost
    participant J as MCP server's OAuth (e.g. api.jam.dev)
    participant O as Owner's browser
    R->>B: POST /api/mcp/client (auth_type oauth, oauth_config with registration_url, scopes)
    B->>J: register a client, redirect_uri = mcp_external_client_url + /api/oauth/callback
    J-->>B: client_id (PKCE, no secret)
    B-->>R: pending_oauth with authorize_url and complete_url
    O->>J: open authorize_url, sign in, approve (Jam: scope mcp:read)
    J->>O: redirect to https://bifrost.weyland.lab/api/oauth/callback
    O->>B: callback with the code
    B->>J: exchange the code for tokens
    R->>B: POST /api/mcp/client/ID/complete-oauth
    B-->>R: 200 MCP client connected successfully with OAuth
```

`mcp_external_client_url` must be the public URL: unset, Bifrost takes the request Host header, and the registrar runs
in-cluster, so the callback became `bifrost.weyland.svc.cluster.local` (found 2026-11-11). Which tools a key then sees is
set separately per key (`register_bifrost_vk_mcp.py`; Jam: read tools only).

The five settings (with `skills_external_client_url`, B241, and `mcp_external_client_url`, B192) live in `config.db` and are restored by `register_bifrost_client_config.py`; VK→MCP scoping by `register_bifrost_vk_mcp.py` (B203); the token is the sealed
`bifrost-setup-token` Secret (runbook § Bifrost setup token).

**Read-only fleet;** write/act tools live on the separate `/mcp-act` mount (Keycloak-authed, `policy.gate`).
Demo: [demos/bifrost.md](../demos/bifrost.md). Runbook: [runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md).
