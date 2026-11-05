# Demo: the Slack feed (B184)

Each source posts to its channel, Telegram still pages, and the free plan's 10-installation cap holds with 3 used
([runbook](../runbooks/slack.md), [concept](../concepts/slack.md), [flow](../diagrams/flow-slack.md)).

## 1. Proven before the push (RUN 2026-11-04/05)

| Check | Result |
|---|---|
| The three `weyland` incoming webhooks (`#alerts`, `#deploys`, `#errors`) | each answered `HTTP 200 ok` to a check message |
| Alertmanager routes (`amtool config routes test`, v0.32.2) | critical → `slack-alerts,linear-incidents,telegram`; warning / info / unlabelled → `slack-alerts,telegram`; Watchdog → `healthchecks-watchdog`; InfoInhibitor → `null`. Telegram pages exactly as before |
| Alertmanager config and Slack templates | `check-config` SUCCESS; color / title / text render |
| Argo CD notifications (`argocd admin notifications`, v3.4.4, against the live `n8n` app) | both triggers parse and evaluate (`false`: n8n is healthy); both templates rendered with real data and Slack answered `200 OK` (`[SYNC FAILED] n8n`, `[DEGRADED] n8n` as forced test renders); the `toJson` body is valid JSON |
| Woodpecker `notify-slack` | `woodpecker-cli lint` valid; the step's `printf` in its own image gave valid JSON; Slack answered `200` (a sample `[CI FAILED] … #999`) |
| GitHub app on free Slack | installed and subscribed to `edtbl76/weyland-lab` (the one claim the audit could not source) |
| Linear app | connected to `#linear-updates` (team EMA: project updates, completed/canceled, triage; initiatives) |

## 2. Live (after the push and the Argo CD `helm upgrade`)

**CLI.**

- Alertmanager: the runbook's warning test alert.

  [rogueone]
  ```
  kubectl -n monitoring run slack-test-alert --rm -i --restart=Never --image=quay.io/prometheus/alertmanager:v0.32.2 --command -- amtool alert add --alertmanager.url=http://monitoring-kube-prometheus-alertmanager.monitoring:9093 alertname=SlackTestAlert severity=warning namespace=monitoring --annotation='summary="B184 Slack test alert"' --annotation='description="Fired by docs/runbooks/slack.md, resolves by itself after 5 min."'
  ```
  Expected: `[FIRING:1] SlackTestAlert (monitoring) [warning]` in `#alerts`, Telegram pages as usual, and `[RESOLVED]`
  about 5–10 minutes later.
- Argo CD: the runbook's filtered `template notify` from the controller. Expected: `HTTP/2.0 200 OK` and
  `[DEGRADED] n8n` in `#deploys`.

**UI.**

- Uptime Kuma: Settings → Notifications → `Slack #alerts` → **Test** posts to `#alerts`.
- GlitchTip: one real test error from `dagster-user-code` (the runbook command) alerts into `#errors`.
- Linear: complete or cancel any issue, and it appears in `#linear-updates`.
- GitHub: the next push appears in `#github`.

**RUN 2026-11-05 (live):**

| Source → channel | Result |
|---|---|
| Alertmanager → `#alerts` | two real warnings (a stale `dashboard-coverage` Job) posted firing, then **resolved** once the Job was deleted; Slack 6 sent / 0 failed, Telegram paged as before |
| Uptime Kuma → `#alerts` | the notification's Test posted |
| Argo CD → `#deploys` | the in-cluster controller's filtered test: `HTTP/2.0 200 OK`, `[DEGRADED] n8n` posted; the controller evaluates both triggers against all 83 apps (3,496 evaluations, 0 sends, 0 errors while everything is healthy) |
| GlitchTip → `#errors` | a test error from `dagster-user-code` posted `GlitchTip Alert: B184 Slack test` (project `weyland-dagster`) at 14:23Z. The first attempt found GlitchTip dropping **every** error after a quiet spell (stale pooled DB connections); fixed with `DATABASE_POOL_MIN_SIZE=0` ([glitchtip.md](../runbooks/glitchtip.md)). **Fix proven 15:00Z:** after 30+ min idle (the condition that dropped every error), `B184 GlitchTip idle-pool proof` landed as an issue and alerted to `#errors`, with 0 envelope 500s and 0 `OperationalError` |
| GitHub → `#github` | the pushes `52a96d1b` and `c78b2278` and PR #303 posted |
| Linear → `#linear-updates` | connected; closing EMA-242 is its live proof |
| Woodpecker → `#deploys` | proven by its payload test; a live post waits for a real red pipeline (none is caused on purpose) |

## Cleanup

Test posts stay in their channels as the record (the free plan drops anything past 90 days anyway). The test pod is
`--rm`, and the test alert resolves by itself. Nothing else is created.
