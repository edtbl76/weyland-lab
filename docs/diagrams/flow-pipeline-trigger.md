# Flow: Pipeline Trigger (`/pipeline/trigger` → Dagster)

How an API/agent call kicks a Dagster run (e.g. on-demand ingestion). The agent path audits this as an
act-tool (see [flow-act-tool.md](flow-act-tool.md)); this diagram is the launch mechanism itself. `job_name`
is an enum of the three jobs, defaulting to `weyland_ingestion_job`. The run proceeds independently (e.g.
[flow-ingestion.md](flow-ingestion.md)); the caller just gets the run id back. **Since B207 (2026-10-14) the launch is
guarded and fails closed:** the mesh admits only the MCP gateway's identity to this path, the guard's `policy.gate`
must allow the actor, and an unreachable guard refuses the act (counted in `tool_server_guard_failures_total`). The
full layer-by-layer picture is arch §10g.

```mermaid
sequenceDiagram
    participant Cl as MCP gateway (/mcp-act)
    participant TS as tool-server /pipeline/trigger
    participant G as weyland-guard /guard/act
    participant DG as Dagster GraphQL endpoint (/graphql)
    participant Run as Dagster run (job)
    Note over Cl,TS: Istio admits only the gateway identity, any other caller gets 403 RBAC
    Cl->>TS: POST /pipeline/trigger {job_name} (enum, default weyland_ingestion_job)
    TS->>G: POST /guard/act {actor, tool} (Istio admits only the tool-server identity)
    alt policy.gate blocks
        G-->>TS: block
        TS-->>Cl: 403 blocked by policy.gate (nothing launches)
    else guard unreachable or garbage
        TS-->>Cl: 403 guard-unavailable (fail closed, counted)
    else allowed
        G-->>TS: allow
        TS->>DG: httpx POST launchRun mutation
        DG->>Run: start
        DG-->>TS: runId
        TS-->>Cl: {status: "ok", run_id, job_name}
    end
    Note over Cl,Run: caller polls run status in the Dagster UI (dagster.weyland.lab)
```
