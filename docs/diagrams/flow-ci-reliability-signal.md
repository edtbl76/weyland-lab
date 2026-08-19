# Flow: CI reliability signal — Woodpecker runs → Port `ci_pipeline` (B63)

How a Woodpecker run's **outcome** reaches Port so a **weyland CI reliability view** can aggregate pass/fail — Port's
stock Reliability/DORA boards read **GitHub Actions only**, so they're blind to weyland (which runs **Woodpecker**,
not Actions). A `notify-port` step POSTs the run's terminal status as JSON to a Port **webhook data source**, mapped
to the **`ci_pipeline`** blueprint (entity id `repo-number`, so every run is its own row → build history). A
`weyland_ci_reliability` dashboard then reads that blueprint (status pie + counters + a runs table).

**Two backends feed the same blueprint, and the notify step differs by backend because of a DAG subtlety:**

- **weyland-lab** (`backend: kubernetes`, **single** workflow) — one `notify-port` step reads `$CI_PIPELINE_STATUS`,
  which is reliable here because the pipeline *is* that one workflow, so its status is final when the last step runs.
- **STUD.io** (`backend: local`, **three** parallel workflows: main · plugin-scanner · roadie) — `$CI_PIPELINE_STATUS`
  reflects the **whole** pipeline, which isn't final while sibling workflows still run, so it reads **empty** at
  main's notify time (and Port silently drops an empty-enum status: ingest returns `ok:true`, but **no entity**).
  Fix: **two status-gated steps** (`notify-port-pass` / `notify-port-fail`) that **hardcode** the status, each
  `depends_on` **every** prior step so they're the terminal stage — without `depends_on` a step's only dependency is
  the implicit clone, so `when: status:` evaluates mid-run and fires a **false green** before scan/e2e/perf finish.
  Only `main` reports (all three workflows share the pipeline number → would collide on the `repo-number` id).

```mermaid
sequenceDiagram
    participant Run as Woodpecker workflow (final stage)
    participant Step as notify-port step (curl, from_secret port_ingest_url)
    participant Ingest as Port ingest URL (ingest.getport.io/<key>)
    participant WH as Port webhook DS woodpecker (mapping)
    participant BP as ci_pipeline blueprint (id = repo-number)
    participant Dash as weyland_ci_reliability dashboard
    Note over Run: run reaches its terminal status (success / failure)
    alt weyland-lab (kubernetes, single workflow)
        Run->>Step: last step; $CI_PIPELINE_STATUS is final here
        Step->>Ingest: POST printf JSON {number,status,repo,branch,commit,event,url}
    else STUD.io (local, 3 parallel workflows)
        Note over Run,Step: notify-port-pass (when:status success) / notify-port-fail (when:status failure)<br/>each depends_on ALL prior steps → terminal stage; status HARDCODED (env var is empty here)
        Run->>Step: whichever gate matches main's real outcome fires
        Step->>Ingest: POST printf JSON with hardcoded status
    end
    Ingest->>WH: webhook DS receives body (filter .body.number != null)
    WH->>BP: upsert entity id = repo-number (slash in repo → dash), props from body
    BP-->>Dash: status pie + count counters + runs table read the blueprint
    Note over Dash: proven — weyland-lab #12 (success) · stud.io #14 (failure) · stud.io #15 (success)
```
