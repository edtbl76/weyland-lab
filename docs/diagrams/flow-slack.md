# Flow: Slack — the feed beside the pager (B184)

Five channels in a free Slack workspace show what the platform is doing. Telegram still pages; Slack posts carry no
@mentions, so nothing pings twice. Runbook: [slack.md](../runbooks/slack.md); concept:
[concepts/slack.md](../concepts/slack.md).

```mermaid
sequenceDiagram
    participant Pr as Prometheus
    participant AM as Alertmanager
    participant TG as Telegram (pager)
    participant AR as Argo CD notifications
    participant WP as Woodpecker
    participant GT as GlitchTip
    participant WH as Slack app weyland (incoming webhooks)
    participant LN as Linear app
    participant GH as GitHub app
    participant SL as Slack channels
    Pr->>AM: alert fires (any severity)
    AM->>WH: slack-alerts receiver (continue)
    WH->>SL: post to alerts channel
    AM->>TG: catch-all route, pages as before
    AR->>WH: app sync failed or health degraded
    WH->>SL: post to deploys channel
    WP->>WH: notify-slack step, only on a failed pipeline
    WH->>SL: post to deploys channel
    GT->>WH: new-error alert (per project)
    WH->>SL: post to errors channel
    LN->>SL: completed or canceled, triage, project and initiative updates
    GH->>SL: issues, PRs, commits of weyland-lab
    Note over WH,SL: one app slot for every webhook tool. Free plan caps installations at 10, 3 used
```

- **No inbound path.** Every arrow into Slack is outbound from the lab or from a vendor's cloud. Slack never calls
  the LAN, so slash commands and buttons are not used.
- **Webhook URLs are secrets.** Sealed for the cluster readers, a Woodpecker repo secret for CI, pasted by the owner
  into the Kuma and GlitchTip UIs. Never in git.
