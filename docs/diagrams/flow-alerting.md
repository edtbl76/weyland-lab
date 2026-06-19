# Flow: Alerting (B5)

Prometheus evaluates alert rules over scraped metrics; Alertmanager groups/dedupes/routes; the operator
gets a Telegram DM. Same Telegram bot surface the agents use, different sender.

```mermaid
sequenceDiagram
    participant Tgt as Scrape targets (nodes / pods / ServiceMonitors / Envoy)
    participant Pr as Prometheus
    participant AM as Alertmanager
    participant Tg as Telegram (operator DM)
    Tgt-->>Pr: metrics (scrape)
    Pr->>Pr: evaluate alert rules
    Pr->>AM: fire alert (threshold breached)
    AM->>AM: group + dedupe + route
    AM->>Tg: notification
    Note over Pr,AM: mesh metrics (Envoy) now flow here too via the B8 PodMonitor
```
