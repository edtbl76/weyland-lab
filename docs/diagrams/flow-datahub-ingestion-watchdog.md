# Flow — DataHub ingestion watchdog (B197)

Once a day at 05:55 NY — after the last daily DataHub ingestion (dbt, 05:00) and the Sunday scans — the watchdog reads
every managed-ingestion source and its recent runs from DataHub's GraphQL API and alerts on the ones that failed,
stopped, or never ran. It reads GMS directly rather than TimescaleDB's nightly copy, so an alert does not wait on (or
inherit the failures of) another job. Operate: [runbooks/datahub.md](../runbooks/datahub.md#ingestion-watchdog-b197-2026-09-28).

```mermaid
sequenceDiagram
    participant C as datahub-ingestion-watchdog (05:55 NY)
    participant G as DataHub GMS GraphQL
    participant AM as Alertmanager to Telegram
    participant K as kube-state-metrics rules
    C->>G: listIngestionSources, 50 per page, last 20 runs each (Bearer token)
    G-->>C: sources + schedules + run history
    alt read failed, errors, empty or partial list
        C-->>K: exit 2, Job fails, ScheduledJobFailed pages
    else every source read
        loop each source
            alt no schedule
                C->>C: skip if an accepted on-demand URN, else Stale
            else never ran
                C->>AM: DataHubIngestionNeverRan
            else latest run FAILURE or ABORTED
                C->>AM: DataHubIngestionFailed
            else no SUCCESS within 2x schedule
                C->>AM: DataHubIngestionStale
            end
        end
        C-->>C: exit 0, or 1 if an alert POST failed
    end
```
