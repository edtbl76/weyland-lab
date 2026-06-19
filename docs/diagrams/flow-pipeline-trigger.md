# Flow: Pipeline Trigger (`/pipeline/trigger` → Dagster)

How an API/agent call kicks a Dagster run (e.g. on-demand ingestion). The agent path audits this as an
act-tool (see [flow-act-tool.md](flow-act-tool.md)); this diagram is the launch mechanism itself. `job_name`
is an enum of the three jobs, defaulting to `weyland_ingestion_job`. The run proceeds independently (e.g.
[flow-ingestion.md](flow-ingestion.md)); the caller just gets the run id back.

```mermaid
sequenceDiagram
    participant Cl as Client (/pipeline/trigger or /mcp-act)
    participant TS as tool-server /pipeline/trigger
    participant DG as Dagster GraphQL endpoint (/graphql)
    participant Run as Dagster run (job)
    Cl->>TS: POST /pipeline/trigger {job_name} (enum, default weyland_ingestion_job)
    TS->>DG: httpx POST launchRun mutation
    DG->>Run: start
    DG-->>TS: runId
    TS-->>Cl: {status: "ok", run_id, job_name}
    Note over Cl,Run: caller polls run status in the Dagster UI (dagster.weyland.lab)
```
