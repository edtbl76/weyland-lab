# Flow: Alert → Linear incident (U14)

A critical alert pages Telegram as before and also becomes a Linear issue, so the estate keeps a record of every
incident: when it fired, when it resolved, and whether it came back. One issue per alert fingerprint. Runbook:
[alert-to-linear.md](../runbooks/alert-to-linear.md).

```mermaid
sequenceDiagram
    participant Pr as Prometheus
    participant AM as Alertmanager
    participant Tg as Telegram (pager)
    participant N as n8n alert-to-linear
    participant L as Linear (team EMA)
    Pr->>AM: critical alert fires
    AM->>N: POST /webhook/alertmanager-incident (route 1, continue)
    AM->>Tg: notification (route 2, explicit critical route)
    N->>L: find issue with label incident + alert-fingerprint marker
    alt no issue, or closed over 24 h ago
        N->>L: issueCreate (Weyland Auto-Filed, Urgent, U14 incident title)
    else closed under 24 h ago (flapping)
        N->>L: issueUpdate to Todo + comment fired again
    else already open (repeat notification)
        N->>N: nothing to write
    end
    N-->>AM: 200 (or 500 on any failure, Alertmanager retries)
    Pr->>AM: alert stops firing
    AM->>N: POST resolved (send_resolved)
    AM->>Tg: resolved notification
    N->>L: commentCreate resolved + issueUpdate to Done
    N-->>AM: 200
```

- **Two routes, not one.** A matching Alertmanager child route claims the alert even with `continue: true`, so the
  incident route is followed by an explicit critical → Telegram route; otherwise Telegram would stop paging criticals.
  Proven with `amtool config routes test` (`linear-incidents,telegram` for critical, `telegram` for warning).
- **Fails closed.** Linear answers a refused GraphQL write with HTTP 200, so the workflow checks every write's
  `success` and answers 500 if any failed; Alertmanager retries and `AlertmanagerFailedToSendAlerts` reaches Telegram.
- **Only Traefik and Alertmanager can reach n8n** (NetworkPolicy `n8n-front-door-only`): n8n webhooks carry no auth.
