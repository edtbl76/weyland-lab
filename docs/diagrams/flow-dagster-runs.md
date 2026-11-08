# Flow — a scheduled Dagster run, its limits and its watchdog (B239)

How a scheduled job runs and how a failure becomes visible. Runs execute inside the user-code pod, one at a time, and
a failure reaches people only as a warning. Operate: [runbooks/dagster.md](../runbooks/dagster.md).

```mermaid
sequenceDiagram
    participant D as dagster-daemon (scheduler, queue, monitoring)
    participant U as dagster-user-code (code server, runs execute here)
    participant P as core Postgres (run + event DB)
    participant W as dagster-freshness-check (CronJob)
    participant A as Alertmanager
    D->>D: schedule tick (times in docs/schedules.md)
    D->>P: enqueue run (QueuedRunCoordinator, concurrency 1)
    D->>U: launch run (DefaultRunLauncher, in-process)
    U->>P: step and run events
    alt run finishes
        U->>P: RUN_SUCCESS or RUN_FAILURE (step errors recorded)
    else over max runtime (4h instance, 30 min tagged jobs)
        D->>U: stop the run (run monitoring)
        U->>P: RUN_FAILURE "Exceeded maximum runtime"
    else process killed from outside (OOM, eviction)
        Note over U,P: no failure event, the pod's logs and events hold the cause
    end
    W->>P: latest run per job, age of last success
    alt last run failed, or no success within budget
        W->>A: DagsterJobFailed / DagsterJobStale (severity warning)
        Note over A: warnings reach chat only, U14 opens Linear incidents for critical alerts
    else healthy
        W-->>W: nothing fired
    end
```

- **Explain a failure:** `scripts/lib/dagster_runs.py` (runbook § Why did a run fail?) reads the same run and event
  records the UI shows.
- **A CLI `dagster job execute` run never reaches the run DB,** so this whole flow, the watchdog included, never sees it.
