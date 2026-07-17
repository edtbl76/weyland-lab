# Flow (E2E) — Store scale: Port action → port-agent (outbound poll) → store-scaler → k8s scale

Cross-system thread of [flow-store-scaler](flow-store-scaler.md) and the [store-scaler](../demos/store-scaler.md)
demo followed straight through: a Port self-service action becomes a live replica change. Port is SaaS (EU org)
and the lab is LAN-only, so the self-hosted **port-agent** connects **outbound** and polls for runs, then POSTs
the resolved `{store, action}` to the in-cluster **store-scaler**, which patches `deployments/scale`. Demo:
[../demos/store-scale-e2e.md](../demos/store-scale-e2e.md).

```mermaid
sequenceDiagram
    actor User
    participant Port as Port cloud<br/>(app.port.io, EU org)
    participant Agent as port-agent<br/>(ns port-agent, POLLING)
    participant Scaler as store-scaler<br/>(data-mesh, FastAPI)
    participant K8s as k8s API<br/>(deployments/scale)
    participant Store as target store<br/>(cockroachdb / mongodb / mysql / gizmosql)
    participant Argo as Argo CD<br/>(data-mesh app, selfHeal)

    User->>Port: run "Scale data-mesh store" (store + wake/sleep)
    Port->>Port: enqueue action run
    Agent->>Port: claim-pending (outbound poll, ~10s)
    Port-->>Agent: {store, action} body
    Agent->>Scaler: POST /scale {store, action}
    Scaler->>Scaler: validate against allowlist
    Scaler->>K8s: patch deployments/scale (replicas 0↔1)
    K8s->>Store: scale up / down
    Scaler-->>Agent: HTTP 200
    Note over User,Store: first connection after wake fails ~10-30s until Ready, then retries
    alt action = sleep (PARKED)
        Argo->>K8s: selfHeal reverts replicas:0 → 1 (~3 min)
    end
```

**One reusable execution path:** any "click a Port button → do X in the cluster" reuses this outbound-poll seam.
Gotcha chain: `STREAMER_NAME: POLLING` (not KAFKA) · EU org → `PORT_API_BASE_URL: https://api.port.io` (US
default 403s) · **Organization** creds not Personal · action needs a templated `body` or inputs arrive `null`.
Sleep is PARKED (Argo `selfHeal` wins over `replicas: 0`); the wake half is the live keeper.
