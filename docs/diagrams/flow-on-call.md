# Flow: on-call — a critical page escalates Telegram → Slack (B184 phase 2)

Critical alerts page through Grafana Cloud IRM (free tier). One responder; the escalation moves across channels until
someone acknowledges. Runbook: [on-call.md](../runbooks/on-call.md).

```mermaid
sequenceDiagram
    participant Pr as Prometheus
    participant AM as Alertmanager
    participant IRM as Grafana Cloud IRM
    participant TG as Telegram DM
    participant SI as Slack incidents channel
    participant TB as Telegram bot (direct)
    Pr->>AM: critical alert fires
    AM->>IRM: webhook (grafana-irm receiver, URL from sealed secret)
    IRM->>SI: alert group with Acknowledge and Resolve buttons
    IRM->>TG: step 1, default rule (0 min)
    Note over IRM: escalation chain weyland-critical waits 5 min
    IRM->>TG: step 3, important rule (5 min)
    IRM->>SI: important rule after its 5 min wait, at-mention in the group thread (10 min)
    TG-->>IRM: Acknowledge (or the Slack button) stops the escalation
    Pr->>AM: alert resolves
    AM->>IRM: resolved, the alert group closes
    Note over AM,TB: if IRM is unreachable, AlertmanagerFailedToSendAlerts (warning) pages through the direct bot
```

- **Outbound only.** Alertmanager calls Grafana Cloud. Slack's buttons call Grafana Cloud, never the LAN.
- **Proven 2026-11-05:** Telegram 1:46, Telegram 1:51, Slack @mention 1:56 (EST). See
  [demos/slack.md](../demos/slack.md) § 3.
