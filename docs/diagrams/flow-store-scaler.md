# Flow — Store scaler (Port → port-agent → store-scaler → k8s)

The reusable **Port → cluster** execution path, built for a store wake/sleep button (2026-07-02). Port is SaaS
(EU org) and the lab is LAN-only, so Port's cloud **cannot reach inbound** — the same wall as GitHub push
webhooks. The self-hosted **port-agent** solves it by connecting **outbound** to Port and **polling** for action
runs (~10s latency), then POSTing the resolved `{store, action}` payload to the in-cluster **store-scaler**
(FastAPI), which validates against an allowlist and patches `deployments/scale`. Only rarely-queried `data-mesh`
stores are in the set — `cockroachdb`, `mongodb`, `mysql`, `gizmosql` (all `Deployment`, replicas 1, `Recreate`).
The plumbing is generic: any "click a Port button → do X in the cluster" reuses it. See
[../runbooks/port-agent-easy-button.md](../runbooks/port-agent-easy-button.md), [../runbooks/keda.md](../runbooks/keda.md),
[../schedules.md](../schedules.md).

**Sleep is PARKED:** the button works end-to-end (verified: sleep → `replicas: 0`, HTTP 200), but the `data-mesh`
Argo app's `selfHeal` reverts `replicas: 0` back to the manifest's `1` within ~3 min. Making sleep stick needs an
`ignoreDifferences` carve-out on `/spec/replicas`; the execution plumbing is the keeper, not the sleep feature.

## Sequence

```mermaid
sequenceDiagram
    actor User
    participant Port as Port cloud<br/>(app.port.io, EU org)
    participant Agent as port-agent<br/>(ns port-agent, POLLING)
    participant Scaler as store-scaler<br/>(data-mesh, FastAPI)
    participant K8s as k8s API<br/>(deployments/scale)
    participant Store as target store<br/>(cockroachdb / mongodb / mysql / gizmosql)
    participant Argo as Argo CD<br/>(data-mesh app, selfHeal)

    User->>Port: run "Scale data-mesh store"<br/>(inputs: store + wake/sleep)
    Agent->>Port: claim-pending (outbound poll, ~10s)
    Port-->>Agent: action run body {store, action}
    Agent->>Scaler: POST /scale {store, action}
    Scaler->>Scaler: validate against allowlist
    Scaler->>K8s: patch deployments/scale (replicas 0↔1)
    K8s->>Store: scale up / down
    Scaler-->>Agent: HTTP 200
    Note over User,Store: first connection after wake fails ~10-30s until Ready, then retries connect
    alt action = sleep (PARKED)
        Argo->>K8s: selfHeal reverts replicas:0 → 1 (~3 min)
    end
```

**Gotcha chain (each cost a loop):** `STREAMER_NAME: POLLING` not KAFKA (no Kafka creds → crashloop) · EU org →
`PORT_API_BASE_URL: https://api.port.io` (US default 403s `claim-pending`) · **Organization** creds not Personal
(Personal 403 on run-claiming) · the action needs a templated `body` or inputs arrive `null` · Helm config change
needs a `rollout restart deploy/port-agent` to remount.
