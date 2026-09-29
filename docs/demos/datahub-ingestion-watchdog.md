# Demo — DataHub ingestion watchdog (B197)

A DataHub ingestion source that fails, stops, or never runs now reaches Telegram the same morning. Sequence diagram:
[../diagrams/flow-datahub-ingestion-watchdog.md](../diagrams/flow-datahub-ingestion-watchdog.md). Runbook:
[../runbooks/datahub.md](../runbooks/datahub.md#ingestion-watchdog-b197-2026-09-28).

**Status: DONE (2026-09-28).**

| Live check | Result |
|---|---|
| In-cluster Job (runbook command) | `checked 17 source(s): 0 alert(s) fired` |
| Alert drill (`ONLY_SOURCE=Trino - Weyland`, `BUDGET_FACTOR=0.0001`) | `ALERT DataHubIngestionStale source='Trino - Weyland'`; active in Alertmanager, receiver `telegram` |
| UAT | owner received the Telegram message |
| CI #202 | 68/68 steps green, including the SonarQube gate |

## CLI walkthrough

Run the watchdog now (the runbook's command):

[mother]
```
kubectl -n weyland create job datahub-ingestion-watchdog-now --from=cronjob/datahub-ingestion-watchdog && kubectl -n weyland wait --for=condition=complete job/datahub-ingestion-watchdog-now --timeout=180s; kubectl -n weyland logs job/datahub-ingestion-watchdog-now; kubectl -n weyland delete job datahub-ingestion-watchdog-now
```
Expect `checked 17 source(s): 0 alert(s) fired`.

Alert drill (one source, budget shrunk so it reads as stale): the runbook's drill command. Expect
`ALERT DataHubIngestionStale source='Trino - Weyland'`.

## UI walkthrough (UAT)

After the drill, one Telegram message from the Weyland Alerts bot: **DataHubIngestionStale** naming
`Trino - Weyland`. Confirm it arrived and names the source. It resolves on its own ~5 minutes later.

## Teardown

The drill's Job is deleted by its own command. The drill alert resolves on its own; nothing else is created.
