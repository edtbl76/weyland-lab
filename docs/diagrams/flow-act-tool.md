# Flow: Audited Act-Tool (`/mcp-act`, B14 read+act)

Read tools live on `/mcp` (open). Action tools live on a **separate `/mcp-act` mount** (`FastApiMCP`,
`include_tags=["mcp-act"]`) — agents must register it explicitly, so **read access never implies act
access**. Every act call passes the **ACT hook** — now the enforcing **`policy.gate`** (identity-required
allowlist + per-actor rate-cap). This is the **weyland-operator** (B66) lane; Claude Code stays read-only on
`/mcp`. The **B17+B19 MCP gateway** (`mcp.weyland.lab`) fronts `/mcp-act` — Keycloak-authed, injecting a
verified actor — and is **LIVE + enforcing** (not future).

```mermaid
sequenceDiagram
    participant Op as weyland-operator (B66)
    participant GW as MCP gateway (mcp.weyland.lab, Keycloak-authed)
    participant MA as tool-server /mcp-act (weyland-act MCP)
    participant TS as tool-server act endpoint
    participant G as Guardrail ACT hook (policy.gate, enforcing)
    participant Dag as Dagster
    participant PG as guardrail_verdicts
    Op->>GW: call act tool w/ Keycloak client_credentials token
    GW->>GW: validate token → inject verified actor = weyland-operator
    GW->>MA: forward act call (pipeline/trigger | evals/run | evals/score)
    MA->>TS: POST /pipeline/trigger (actor = weyland-operator)
    TS->>G: _guard(ACT, {tool, params, actor})
    G->>PG: gate verdict (allow if actor allowlisted + under rate-cap, else block)
    TS->>Dag: launchRun(job_name)
    Dag-->>TS: runId
    TS-->>MA: {runId}
    MA-->>Op: result
    Note over GW,TS: B17+B19 gateway LIVE + enforcing — policy.gate blocks acts with no verified actor. /mcp stays open (read-only)
```
