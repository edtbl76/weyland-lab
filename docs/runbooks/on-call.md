# On-call runbook (B184 phase 2)

**Critical** alerts page through **Grafana Cloud IRM** (free tier): a weekly rotation, an escalation chain, and
acknowledge / resolve / silence straight from Telegram. Everything below critical still goes to the direct Telegram
bot, and every alert is also in Slack `#alerts` (the feed). Chosen 2026-11-05 over ilert, PagerDuty, Keep and the
rest ([concepts/slack.md](../concepts/slack.md) § On-call).

| | |
|---|---|
| Tool | Grafana Cloud IRM, stack `weyland`, free tier ("Always free", 3 active IRM users) |
| Source | Alertmanager receiver `grafana-irm` → the IRM **Alertmanager integration** `weyland-alertmanager`; URL in sealed Secret `monitoring/grafana-irm` ([secrets.md](secrets.md) § On-call) |
| Responder | the owner, `ed@timberbacklabs.com` (IRM user `ed03`). **One responder, by decision** (2026-11-05): a second login invented only to rotate with was "stupid" (owner), so the exercised path is **escalation across channels**: Telegram first, Slack if not acknowledged |
| Channels | Telegram DM (first), a Slack mention (on escalation), and Slack `#incidents` (each alert group posts there with Acknowledge/Resolve buttons; IRM is SaaS, so Slack's buttons reach Grafana Cloud, never the LAN) |
| What leaves the LAN | alert labels and annotations (the same class of data Telegram already gets) |

## Routing (Alertmanager)

1. Everything → Slack `#alerts` (`continue`).
2. Critical → the U14 Linear incident (`continue`).
3. **Critical → `grafana-irm`** (claims it, so the direct bot does not double-page).
4. Everything else → the direct Telegram bot.

**If IRM is unreachable:** the failed delivery fires `AlertmanagerFailedToSendAlerts`. That alert is a warning, so it
pages through the direct bot: a broken IRM still reaches you. Its critical twin, `AlertmanagerClusterFailedToSendAlerts`,
routes to the broken IRM, so the warning is the one that counts.

Prove a change before it ships:

[rogueone]
```
python3 -c "import yaml;yaml.safe_dump(yaml.safe_load(open('/home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml'))['alertmanager']['config'],open('/tmp/am.yaml','w'))" && for t in "severity=critical" "severity=warning"; do docker run --rm -v /tmp/am.yaml:/c/am.yaml:ro --entrypoint amtool quay.io/prometheus/alertmanager:v0.32.2 config routes test --config.file=/c/am.yaml alertname=X $t; done
```
Expected: `slack-alerts,linear-incidents,grafana-irm`, then `slack-alerts,telegram`.

## The IRM configuration (UI; it is not in git)

IRM's state lives in Grafana Cloud, so this table is its record. If the stack is lost, rebuild it from here.

| Object | Setting |
|---|---|
| Integration | type **Alertmanager**, name `weyland-alertmanager`, default route → escalation chain `weyland-critical`, Slack channel `#incidents` |
| Slack app | IRM's Slack app in the `weyland` workspace (the 4th of Slack's 10 free installs); default channel for alert groups `#incidents` |
| Schedule `weyland-primary` | one rotation: `ed03`, weekly, from a Monday 09:00 America/New_York, all day (on call 24/7). It keeps on-call explicit and allows a hand-off by override |
| Escalation chain `weyland-critical` | 1. notify users from on-call schedule `weyland-primary` (default) → 2. wait 5 min → 3. notify users from on-call schedule `weyland-primary` (**important**) |
| Personal notification rules | **default:** Telegram. **Important:** Telegram → wait 5 min → Slack mention |

Acknowledge stops the escalation; resolve closes the alert group (Alertmanager's resolved notification does it too).

## Test

A critical test page straight into Alertmanager. Leave it **unacknowledged** to prove the escalation: Telegram at 0 min,
Telegram again (the important rule) at about 5, and a Slack mention at about 10, with the alert group in `#incidents`
throughout. Then acknowledge it, from Telegram or the Slack button:

[rogueone]
```
kubectl -n monitoring run oncall-test-page --rm -i --restart=Never --image=quay.io/prometheus/alertmanager:v0.32.2 --command -- amtool alert add --alertmanager.url=http://monitoring-kube-prometheus-alertmanager.monitoring:9093 --end="$(date -u -d '+20 min' +%Y-%m-%dT%H:%M:%SZ)" alertname=OnCallTestPage severity=critical namespace=monitoring --annotation='summary="B184 on-call test page"' --annotation='description="Fired by docs/runbooks/on-call.md: leave unacknowledged to watch the escalation."'
```

It lives 20 minutes (`--end`), so the 10-minute escalation is not cut short by a resolve. **Re-running it while an earlier
test page is still active does NOT page again:** Alertmanager groups by `alertname` + `namespace`, so a second page with
the same two labels joins the first group, and IRM files it under that (likely acknowledged) alert group (found
2026-11-05). For a repeat inside 20 minutes, change both, e.g. `alertname=OnCallTestPage2 namespace=oncall-test`. It also opens a U14
Linear incident (`U14 incident — OnCallTestPage (monitoring)`) and posts to `#alerts`; all three close when it ends. **Handoff between people** is not exercised: the lab has one responder (owner decision); a schedule override
would hand off to anyone added later.

**Proven 2026-11-05:** Telegram 1:46, Telegram 1:51, Slack @mention 1:56 (EST), as above;
[demos/slack.md](../demos/slack.md) § 3.

## Linear triage responsibility — not done, by cost

Rotating Linear's triage responsibility from an on-call schedule needs **Linear Business or Enterprise** (Linear docs,
"Triage"). The workspace is on Free, so no tool can do it at $0. It is recorded as cost-gated, not built around.
