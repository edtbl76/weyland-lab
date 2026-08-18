# Demo — STUD.io CI on the weyland Woodpecker farm (B57b)

STUD.io's full CI suite runs on **weyland's shared Woodpecker server**, not its own retired local one. One server
hosts a **mixed fleet** routed by the built-in `backend` agent label: weyland jobs = `kubernetes` (pods on the
mother agents); STUD.io jobs = `local` (steps on rogueone's host shell + native docker, where the real
Go/Node/pyenv/Playwright toolchain lives). Two LAN NodePorts bridge off-cluster: **`:30900`** (gRPC) for the local
agents to register, **`:30980`** (HTTP) for `woodpecker-cli` to drive the server past `traefik-forward-auth`
(Keycloak 302-redirects Bearer API calls, so the public URL can't be used by a CLI). The LAN box gets **no GitHub
push webhooks** → runs are triggered by CLI (auto-trigger is B57a). Validated live 2026-08-17 (pipelines #5–#10).

## Sequence diagram

Reused from [../diagrams/flow-woodpecker-studio-ci.md](../diagrams/flow-woodpecker-studio-ci.md):

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
    Ag->>Roadie: git clone → roadie build --schema-only / test unit·pbt·e2e·scan·perf
    Roadie->>Dkr: docker exec studio_db psql (schema + seeds → masterdb_test_ci); containerized test lanes
    Roadie->>Ext: sonar-scanner → SonarQube :30969 · plugin-scanner release → MinIO :30990
    Ag-->>Srv: stream logs + status over gRPC
    Op->>Srv: pipeline ps <n> (poll) via :30980
    Srv-->>Op: per-step state → success
```

## Prerequisites
- Woodpecker server up in ns `woodpecker` (v3.17), behind `woodpecker.weyland.lab` (Keycloak SSO for the UI).
- Both LAN NodePorts synced (Argo apps `woodpecker-grpc` + `woodpecker-http` in `raw-extras.yaml`):
  `192.168.1.243:30900` (gRPC) and `192.168.1.243:30980` (HTTP).
- STUD.io's 4 `backend: local` agents active on rogueone (`woodpecker-agent-1..4`, registered agent_id 4–7),
  each with `DOCKER_HOST=unix:///var/run/docker.sock` + `PLAYWRIGHT_BROWSERS_PATH`.
- `woodpecker-cli` (v3.17) at `~/.local/bin/woodpecker-cli`; creds in `~/.config/studio/woodpecker-cli.env`
  (`WOODPECKER_SERVER=http://192.168.1.243:30980` + the PAT — gitignored, never printed/committed).
- Repo `edtbl76/stud.io` secrets present on the server (`sonar_token`, `minio_svc_access_key`,
  `minio_svc_secret_key`; events `push`,`manual`).

## UI walkthrough (eyes-on UAT)
1. Open `https://woodpecker.weyland.lab` (Keycloak login).
2. Select the **`edtbl76/stud.io`** repo → the run list.
3. Open the latest run. **UAT — visually confirm:**
   - all **4 workflows** are present — `main`, `pilot`, `plugin-scanner`, `roadie`;
   - `main` shows every step green: **clone · build · npm-install · unit-pbt · e2e · scan · perf**;
   - the run's agent is a **local** agent (step host = rogueone), not a k8s pod;
   - open `main → scan` logs and confirm the `sonar` sub-steps (pytest-coverage, sonar-scanner) succeeded.
4. Cross-check the SonarQube project updated: `http://192.168.1.243:30969/dashboard?id=controlroom`.

## CLI walkthrough
[rogueone] Load CLI creds + PATH (points at the `:30980` HTTP NodePort — no `kubectl port-forward` needed):
```
. ~/.config/studio/woodpecker-cli.env; export PATH="$HOME/.local/bin:$PATH"
```
[rogueone] Confirm the HTTP NodePort answers and the CLI authenticates:
```
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.1.243:30980/ && woodpecker-cli repo ls | grep stud.io
```
[rogueone] Trigger a run of all 4 STUD.io workflows on the farm:
```
woodpecker-cli pipeline create edtbl76/stud.io --branch main
```
[rogueone] Poll a run to completion (replace N with the number printed above):
```
woodpecker-cli pipeline ps edtbl76/stud.io N
```
[rogueone] Tail a specific step's log (STEP = the step id from `pipeline ps`, e.g. the `main → scan` step):
```
woodpecker-cli pipeline log show edtbl76/stud.io N STEP
```

## Expected result
- `pipeline create` returns a pending run; within minutes every step across all 4 workflows reaches `success`.
- `main`: clone · build · npm-install · unit-pbt · e2e · scan · perf all green (e2e = 4 Playwright shards over
  `masterdb_test_ci_0..3`; scan = sonar · trivy · detect-secrets · security-headers · govulncheck · gosec ·
  staticcheck).
- The run executes on a **local** agent (host shell + native docker), proving the mixed-fleet routing.

## Cleanup / teardown
CI runs create isolated test databases on `studio_db` (`masterdb_test_ci` + the e2e shard clones
`masterdb_test_ci_0..3`); they are reused across runs but leave residue. To remove them:
```
for db in masterdb_test_ci masterdb_test_ci_0 masterdb_test_ci_1 masterdb_test_ci_2 masterdb_test_ci_3; do docker exec studio_db dropdb -U studio --if-exists "$db"; done
```
The production `masterdb` is never touched (roadie's `guardNoProdDB` refuses to apply schema to it).
