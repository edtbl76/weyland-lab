# Flow: Audited Act-Tool (`/mcp-act`, B14 read+act)

Read tools live on `/mcp` (open). Action tools live on a **separate `/mcp-act` mount** (`FastApiMCP`,
`include_tags=["mcp-act"]`) — agents must register it explicitly, so **read access never implies act
access**. Every act call passes the **ACT hook** (`policy.audit`, shadow → audited, not yet enforced).
This is the Hermes operator lane; Claude Code stays read-only on `/mcp`. Enforcing gate + gateway fronting
= B35 / B17+B19.

```mermaid
sequenceDiagram
    participant Op as Hermes operator
    participant MA as tool-server /mcp-act (weyland-act MCP)
    participant TS as tool-server act endpoint
    participant G as Guardrail ACT hook (policy.audit, shadow)
    participant Dag as Dagster
    participant PG as guardrail_verdicts
    Op->>MA: call act tool (pipeline/trigger | evals/run | evals/score)
    MA->>TS: POST /pipeline/trigger (actor = X-Forwarded-Consumer)
    TS->>G: _guard(ACT, {tool, params, actor})
    G->>PG: audit verdict (shadow)
    TS->>Dag: launchRun(job_name)
    Dag-->>TS: runId
    TS-->>MA: {runId}
    MA-->>Op: result
    Note over MA,TS: future B17+B19 gateway fronts /mcp-act with auth/policy. /mcp stays open
```
