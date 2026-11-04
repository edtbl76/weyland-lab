# Demo: a critical alert becomes a Linear incident (U14)

A critical Alertmanager alert opens one Linear issue, a repeat does not duplicate it, the resolve closes it, a re-fire
inside 24 h reopens the same issue, and Telegram pages throughout ([runbook](../runbooks/alert-to-linear.md),
[flow](../diagrams/flow-alert-to-linear.md)). Part 1 was RUN 2026-11-04. Part 2 is the live check after the owner's
install steps.

## 1. Rehearsal: the git workflow in a fresh n8n, against real Linear (RUN 2026-11-04)

The cluster's pinned image (`n8nio/n8n@sha256:9cb6…`, n8n 2.29.10) in a throwaway local container with an empty data
directory: a credential named as the file names it, but with a **different id** than the workflow file names, then the
runbook's import and publish, then Alertmanager-shaped payloads POSTed to the webhook. Results (RUN):

| Payload | Webhook answer | Linear |
|---|---|---|
| not an Alertmanager body | **500** `payload has no alerts[]` | nothing |
| `severity=warning` firing | 200, nothing to do | nothing |
| critical firing | 200 `create EMA-326` | EMA-326 `U14 incident — U14TestAlert (n8n)`, Todo, Urgent, label `incident`, project Weyland Lab |
| the same firing again | 200, nothing to do | still one issue |
| resolved | 200 `close EMA-326` | comment `Resolved at …`, Done |
| resolved again | 200, nothing to do | unchanged |
| firing again (flap) | 200 `reopen EMA-326` | comment `Fired again …`, Todo |
| resolved | 200 `close EMA-326` | Done |
| firing, credential swapped to an invalid key | **500** | nothing |

Also shown: the import re-bound the credential by name (export showed `localTestCredId1` on both HTTP steps); export
to stdout is corrupted by n8n's `Error tracking disabled …` line, so the runbook exports to a file; the CLI import
works while the server runs. Routing (RUN, `amtool config routes test`, Alertmanager v0.32.2, the committed values):

```
alertname=X severity=critical        -> linear-incidents,telegram
alertname=X severity=warning         -> telegram
alertname=Watchdog severity=none     -> healthchecks-watchdog
alertname=InfoInhibitor severity=none -> null
```

## 2. Live: the cluster, end to end (owner, after the install steps)

**CLI.** Fire the runbook's test alert (one-off `amtool` pod in `monitoring`):

[rogueone]
```
kubectl -n monitoring run u14-test-alert --rm -i --restart=Never --image=quay.io/prometheus/alertmanager:v0.32.2 --command -- amtool alert add --alertmanager.url=http://monitoring-kube-prometheus-alertmanager.monitoring:9093 alertname=U14TestAlert severity=critical namespace=n8n --annotation='summary="U14 test alert"' --annotation='description="Fired by docs/runbooks/alert-to-linear.md, resolves by itself after 5 min."'
```

Run it twice within a minute. Expect: one Telegram message per notification, and exactly one new issue
`U14 incident — U14TestAlert (n8n)`. About 5–10 minutes later: a Telegram "resolved" message, and the issue Done with a
`Resolved at …` comment.

**RUN 2026-11-04 (live):**
- the test alert opened EMA-329 at 18:25 and closed it at 18:30;
- re-fired at 19:53, it **reopened EMA-329** (comment `Fired again …`, no new issue) and closed it at 19:59;
- two real criticals opened EMA-327 (`AlertmanagerClusterFailedToSendAlerts`) and EMA-328 (`ScheduledBackupFailed`), and
  each closed itself when its alert resolved;
- Telegram paged throughout, with 0 Telegram and 0 webhook failures in the window.

**UI.**
- Linear: filter label `incident`. The issue's description carries the alert's summary, its label table, and the
  `alert-fingerprint:` line, and its activity shows the close.
- n8n (https://n8n.weyland.lab), Executions: the runs of `alert-to-linear (U14)`, each green, one per notification.

## Cleanup

Nothing to tear down. The Done test issue is the record of the run: leave it. The one-off pod deletes itself (`--rm`),
and the rehearsal's local container and data directory were removed.
