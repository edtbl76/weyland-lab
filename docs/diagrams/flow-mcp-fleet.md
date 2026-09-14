# Flow: MCP fleet — composed read-only server fleet (B17+B19 Phase 3)

The operator reasons over 6 read-only MCP servers (one per subsystem) aggregated by the compositor and fronted at
`/mcp-fleet`. Brain = Haiku via LiteLLM. Acts stay gated on the separate `/mcp-act` path.

```mermaid
sequenceDiagram
    autonumber
    participant U as You (Telegram)
    participant OP as Operator (B66)<br/>Haiku via LiteLLM
    participant GW as Gateway /mcp-fleet
    participant C as Compositor (FastMCP)
    participant S as Fleet server<br/>(trino · k8s · grafana · postgres · neo4j · datahub)
    U->>OP: "list the trino catalogs"
    OP->>OP: brain selects a fleet tool
    OP->>GW: MCP tools/call (e.g. trino_list_catalogs)
    GW->>C: route to the owning server
    C->>S: invoke (read-only)
    S-->>C: live data
    C-->>GW: result
    GW-->>OP: tool result
    OP-->>U: grounded answer
    Note over OP,GW: an act like "run the ingestion pipeline" returns a Confirm prompt, and the /mcp-act path with policy.gate stays separate and gated
```

Demo: [demos/mcp-fleet.md](../demos/mcp-fleet.md). Runbook: [runbooks/mcp-fleet.md](../runbooks/mcp-fleet.md).
