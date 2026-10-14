# Flow — write surfaces and their front doors (B209)

Who may change state, and what refuses everyone else. Design: [design/write-surfaces.md](../design/write-surfaces.md);
runbook: [runbooks/write-surfaces.md](../runbooks/write-surfaces.md); demo: [demos/act-guard.md](../demos/act-guard.md)
§ Write surfaces.

## A call to a write surface

```mermaid
sequenceDiagram
    participant P as a pod (any)
    participant NP as NetworkPolicy (k3s controller)
    participant D as dagster-webserver :3000
    participant UC as dagster-user-code
    participant TR as Traefik (kube-system)
    participant KC as Keycloak forward-auth
    participant R as realm-of-agents :8080
    P->>NP: POST /graphql launchRun
    NP-->>P: refused (meshed caller: instant envoy 503)
    UC->>NP: POST /graphql (FR-DRAIN, TXN, launchRun runbook)
    NP->>D: admitted (app=dagster-user-code)
    D-->>UC: 200
    TR->>KC: browser request to realm.weyland.lab
    KC-->>TR: no session: 307 to Keycloak
    TR->>NP: signed-in request
    NP->>R: admitted (kube-system traefik)
    R-->>TR: Console / A2A, free lane unless allow_paid true
```

## Keeping it closed

```mermaid
flowchart LR
    REG["applications.yaml<br/>every deployed service: writes true|false"] --> G{"check-write-surfaces.sh<br/>(repo-guards)"}
    K8S["k8s/**: NetworkPolicy podSelector,<br/>AuthorizationPolicy selector (app=…)"] --> G
    G -->|"writes: false"| OK1["read-only"]
    G -->|"a policy selects app=pod_app or key"| OK2["policy"]
    G -->|"front_door: how the app authenticates"| OK3["front door"]
    G -->|"accepted_gap: B211 …"| GAP["tracked gap, printed every run"]
    G -->|"none of these / writes undeclared"| FAIL["exit 1: named"]
    G -->|"registry unreadable, no policies parsed"| CANT["exit 2: could not check"]
```

- **Why NetworkPolicy, not Istio, here:** Traefik, port-agent and store-scaler are unmeshed, so they have no SPIFFE
  identity for an AuthorizationPolicy to name. A principal-based ALLOW would have refused the Dagster UI.
- **Labels are the identity:** `scripts/tests/write-surface-netpol.bats` pins each policy's target and its exact
  callers against the Deployments' pod labels, so a typo can't silently open a surface or lock a caller out.
