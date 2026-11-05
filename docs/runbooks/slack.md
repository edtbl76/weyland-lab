# Slack runbook (B184)

A free Slack workspace is the lab's **feed**: what is firing, deploying, erroring and moving in Linear and GitHub, in
the chat surface a real org would use. **Telegram stays the only pager.** Slack posts carry no @mentions, so nothing
pings twice. Audit and routing decisions: [concepts/slack.md](../concepts/slack.md).

## The free plan, and how the design fits it

Verified 2026-11-04 (Slack help center, "Feature limitations on the free version of Slack"): **at most 10
installations** (third-party or custom apps), 90 days of message history, no workflows, canvases, lists or user groups. So:
- One custom app, **`weyland`**, holds every incoming webhook (one per channel). Every tool that can post to a webhook
  shares that **one** slot.
- Only tools that need their own app spend a slot: **Linear** and **GitHub** today. **3 of 10 used.**
- The lab is LAN-only, so nothing that needs Slack to call *into* the lab (slash commands, buttons) is used. The
  Linear and GitHub apps run Slack ↔ their cloud and never reach the lab.

## Channel map

| Channel | Source | Mechanism | Posts |
|---|---|---|---|
| `#alerts` | Alertmanager | `weyland` webhook, `api_url_file` from Secret `monitoring/slack-webhooks` | every alert except InfoInhibitor and Watchdog, firing and resolved |
| `#alerts` | Uptime Kuma | `weyland` webhook, set in Kuma's UI | monitor down / up |
| `#deploys` | Argo CD notifications | `weyland` webhook | sync failed, health degraded, deployed |
| `#deploys` | Woodpecker | `weyland` webhook, a `curl` step on failure | pipeline failed |
| `#errors` | GlitchTip | `weyland` webhook, set per project in GlitchTip's UI | new error alert |
| `#linear-updates` | Linear Slack app | Linear's app (1 slot) | issue completed / canceled, added to triage, project and initiative updates |
| `#github` | GitHub app for Slack | GitHub's app (1 slot) | `edtbl76/weyland-lab`: issues, PRs, commits, releases, deployments |

Webhook URLs live in the gitignored `scripts/.env` (`SLACK_WEBHOOK_ALERTS` / `_DEPLOYS` / `_ERRORS`). They are
secrets: anyone holding one can post. Sealing and rotation: [secrets.md](secrets.md) § Slack webhooks.

## Alertmanager → `#alerts`

Route tree (`k8s/monitoring/kube-prometheus-stack-values.yaml`):
1. InfoInhibitor → `null`;
2. Watchdog → healthchecks;
3. **everything → `slack-alerts`, `continue: true`**;
4. critical → `linear-incidents`, `continue: true` (U14);
5. **catch-all → `telegram`**.

A matching child route claims the alert even with `continue`, and the parent's default receiver fires only when no
child matched. Step 3 matches everything, so without step 5 Telegram would stop paging.

Prove any change before it ships:

[rogueone]
```
python3 -c "import yaml;yaml.safe_dump(yaml.safe_load(open('/home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml'))['alertmanager']['config'],open('/tmp/am.yaml','w'))" && for t in "severity=critical" "severity=warning" "alertname=Watchdog"; do docker run --rm -v /tmp/am.yaml:/c/am.yaml:ro --entrypoint amtool quay.io/prometheus/alertmanager:v0.32.2 config routes test --config.file=/c/am.yaml alertname=X $t; done
```
Expected: `slack-alerts,linear-incidents,telegram`, then `slack-alerts,telegram`, then `healthchecks-watchdog`.

## Test

Fires a warning test alert straight into Alertmanager from a one-off pod. It reaches `#alerts` (and Telegram, which
pages as usual) within about a minute, and resolves by itself after 5 minutes:

[rogueone]
```
kubectl -n monitoring run slack-test-alert --rm -i --restart=Never --image=quay.io/prometheus/alertmanager:v0.32.2 --command -- amtool alert add --alertmanager.url=http://monitoring-kube-prometheus-alertmanager.monitoring:9093 alertname=SlackTestAlert severity=warning namespace=monitoring --annotation='summary="B184 Slack test alert"' --annotation='description="Fired by docs/runbooks/slack.md, resolves by itself after 5 min."'
```

Expected in `#alerts`: `[FIRING:1] SlackTestAlert (monitoring) [warning]` (yellow), then about 5–10 minutes later
`[RESOLVED] …` (green). A failed delivery shows in `alertmanager_notifications_failed_total{integration="slack"}` and
fires `AlertmanagerFailedToSendAlerts`.

## Argo CD → `#deploys`

Config: `k8s/argocd/argocd-values.yaml` § `notifications` (Argo CD is installed by `helm upgrade`, not by Argo; see
[argocd.md](argocd.md)). The generic `webhook` service named `slack-deploys`; URL `$slack-webhook-deploys` from the
sealed `argocd/argocd-notifications-secret`. Default subscription for every app: `on-sync-failed`,
`on-health-degraded`. **Not `on-deployed`**: every app tracks `main`, so each push gives ~83 apps a new revision and
would post ~83 messages.

Apply a change (the owner; the secret must exist first, see [secrets.md](secrets.md) § Slack webhooks):

[rogueone]
```
helm upgrade argocd argo-cd --repo https://argoproj.github.io/argo-helm --version 9.6.0 -n argocd -f /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/argocd/argocd-values.yaml
```

Prove a config change without sending: `trigger get`, `template get` and `trigger run` evaluate against a live app
and never print the secret. A real send through `template notify` **prints the full request, webhook URL included**
(found 2026-11-05), so filter it to the status line. This runs in the controller, read-only on the app:

[rogueone]
```
kubectl -n argocd exec deploy/argocd-notifications-controller -- argocd admin notifications template notify slack-health-degraded n8n --recipient slack-deploys 2>&1 | grep -oE 'HTTP/[0-9.]+ [0-9]+ [A-Za-z]+' | head -1
```
Expected: `HTTP/2.0 200 OK`, and a `[DEGRADED] n8n` test message in `#deploys` (a forced render: n8n is healthy).

## Woodpecker → `#deploys`

Step `notify-slack` in `.woodpecker.yml` runs only when the pipeline fails, and posts
`[CI FAILED] <repo> #<n> on <branch>` with the pipeline link. The URL is the repo secret `slack_webhook_deploys`
([woodpecker.md](woodpecker.md) § repo secrets); it must exist before any config that references it, or the whole
config fails to parse. It is proven by the next red pipeline. A deliberate failure is not run just to test it.

## Uptime Kuma → `#alerts`

Set in Kuma's UI (its state is its own SQLite DB, not git): Settings → Notifications → **Slack #alerts** (type Slack,
the `SLACK_WEBHOOK_ALERTS` URL, default-enabled, applied to all monitors). The Telegram notifier stays as the pager.
Test: the notification's **Test** button in that dialog posts a test message to `#alerts`. A new monitor gets it
automatically only because it is default-enabled.

## GlitchTip → `#errors`

Set per project in GlitchTip's UI: project → Settings → **Alerts** → recipient **Webhook** = the
`SLACK_WEBHOOK_ERRORS` URL. A new project needs it added; GlitchTip has no global alert. GlitchTip has **no test
button** (none in its docs, checked 2026-11-05), so test with one real error event. The Dagster project's DSN is already
in `dagster-user-code` (12 GiB limit, so a second interpreter is safe), and no secret leaves the cluster:

[rogueone]
```
kubectl -n weyland exec deploy/dagster-user-code -c dagster-user-code -- python3 -c "import os,sentry_sdk;sentry_sdk.init(os.environ['SENTRY_DSN']);print(sentry_sdk.capture_message('B184 Slack test: GlitchTip to #errors',level='error'));sentry_sdk.flush()"
```
Expected: an event id printed, a new issue in GlitchTip's Dagster project, and its alert in `#errors` (within the
alert's time window). Resolve the test issue in GlitchTip afterwards.

## Linear → `#linear-updates`, GitHub → `#github`

Both are vendor apps (one slot each). They talk Slack ↔ their cloud, never the lab.
- **Linear**: Linear Settings → Integrations → Slack. Team EMA → Slack notifications → `#linear-updates` with **new
  project update**, **completed or canceled**, **added to triage** (issue added, status change and comments are off:
  at the lab's issue rate they would flood). Settings → Initiatives → Slack notifications → `#linear-updates`. The
  channel is not `#linear`, because that name is taken by the Linear app's own user.
- **GitHub**: the GitHub app for Slack, `/github subscribe edtbl76/weyland-lab` in `#github`. It works on free Slack
  (installed 2026-11-04).

## Adding an integration

Count the slots first: Slack → Settings & administration → Manage apps. A webhook tool reuses the `weyland` app: add
a webhook for its channel in the app's Incoming Webhooks page, put the URL in `scripts/.env`, seal it if a cluster
workload reads it ([secrets.md](secrets.md)), and add a row to the channel map above and to
[concepts/slack.md](../concepts/slack.md).
