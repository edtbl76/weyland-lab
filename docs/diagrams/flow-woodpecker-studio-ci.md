# Flow: STUD.io CI on the weyland Woodpecker farm (B57b)

How a STUD.io CI run executes on weyland's **shared** Woodpecker server — a **mixed fleet** on one server routed
by the built-in `backend` agent label: weyland's own jobs run `backend: kubernetes` (steps = pods on the mother
agents); STUD.io's jobs run `backend: local` (steps run on rogueone's **host shell**, which carries the real
Go/Node/pyenv/Playwright toolchain + native docker). Two LAN NodePorts make it work from outside the cluster:
**`:30900`** (gRPC) is how the off-cluster local agents register, and **`:30980`** (HTTP) is how `woodpecker-cli`
drives the server — it bypasses `traefik-forward-auth` (Keycloak), which 302-redirects Bearer API calls and so
can't be used by a CLI. The LAN box gets **no GitHub push webhooks**, so runs are triggered manually / by CLI
(the automatic-trigger track is B57a).

```mermaid
sequenceDiagram
    participant Op as Operator (rogueone)
    participant CLI as woodpecker-cli
    participant Srv as Woodpecker server (ns woodpecker, v3.17)
    participant Ag as local-backend agent (rogueone host, backend=local)
    participant Roadie as roadie (/usr/local/bin/roadie)
    participant Dkr as native docker (studio_db + test images)
    participant Ext as weyland SonarQube :30969 / MinIO :30990
    Op->>CLI: pipeline create edtbl76/stud.io --branch main
    CLI->>Srv: POST /api/... (Bearer PAT) via HTTP NodePort 192.168.1.243:30980
    Note over Srv: enqueues 4 workflows (main · pilot · plugin-scanner · roadie), each labels{backend: local}
    Srv->>Ag: dispatch steps over gRPC NodePort 192.168.1.243:30900 (matched by backend=local)
    Ag->>Ag: git clone into per-run workspace
    Ag->>Roadie: roadie build --schema-only / test unit·pbt·e2e·scan·perf
    Roadie->>Dkr: docker exec studio_db psql (schema + seeds → masterdb_test_ci)
    Roadie->>Dkr: containerized lanes (backend/frontend/go test images; sonar pytest-coverage)
    Roadie->>Ext: sonar-scanner → SonarQube :30969 · plugin-scanner release → MinIO :30990
    Dkr-->>Roadie: results
    Roadie-->>Ag: step exit codes + logs
    Ag-->>Srv: stream logs + status over gRPC
    Op->>Srv: pipeline ps <n> (poll) via :30980
    Srv-->>Op: per-step state → success
    Note over Srv,Ag: weyland's OWN pipeline uses backend: kubernetes → steps run as pods on the mother agents (same server, different lane)
```
