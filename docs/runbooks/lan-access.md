# LAN access — NodePorts only, never port-forward

How anything off the cluster (rogueone: scripts, DataGrip/IntelliJ, the trainers, the CLI tools) reaches an in-cluster
service. **One way: the service's LAN NodePort on mother, `192.168.1.243:<nodePort>`.** Never `kubectl port-forward`,
never IntelliJ's Kubernetes "Forward Ports", never the Python client's `portforward` — a forward is a background
process with a teardown burden that dies silently, and it bypasses the NetworkPolicy that decides who may connect. A
NodePort is a standing endpoint the policy can pin. The rule is an `AGENTS.md` hard rule and is enforced in CI by
`scripts/check-no-port-forward.sh` (below).

A service that is ClusterIP-only **on purpose** is reached by running the work in-cluster (a Job from its CronJob,
`kubectl exec`), not by forwarding: **weyland-postgres** (STRICT mTLS — a plain client off the mesh cannot connect;
query it in-pod, [query/postgres.md](../query/postgres.md)) and **trino-noauth** (strips auth; still deployed until B233's
stage 3, with no repo caller since B233 — the datahub-coverage guard now logs in to Trino directly as an in-cluster
Job, [observability.md](observability.md)).

## The NodePorts

All on mother, `192.168.1.243`. Manifest paths are under `nodes/mother/lab/weyland-platform/`.

| Service | NodePort | Manifest |
|---|---|---|
| Argo CD (CLI) | `192.168.1.243:30880` | `k8s/argocd/argocd-lan.yaml` |
| Cassandra | `:30942` | `k8s/data-mesh/tier2-lan.yaml` |
| ClickHouse (HTTP) | `:30123` | `k8s/data-mesh/tier2-lan.yaml` |
| CockroachDB (pg-wire) | `:30257` | `k8s/data-mesh/tier2-lan.yaml` |
| MongoDB | `:30017` | `k8s/data-mesh/tier2-lan.yaml` |
| MySQL | `:30306` | `k8s/data-mesh/tier2-lan.yaml` |
| TimescaleDB (pg-wire) | `:30543` | `k8s/data-mesh/tier2-lan.yaml` |
| GizmoSQL | `:31337` | `k8s/data-mesh/gizmosql.yaml` |
| lakeFS | `:30800` | `k8s/data-mesh/lakefs.yaml` |
| MinIO S3 | `:30990` | `k8s/minio/minio-s3-lan.yaml` |
| MLflow (+ AI Gateway API) — **rogueone only** | `:30500` | `k8s/mlflow/mlflow.yaml` (+ `netpol.yaml`) |
| LiteLLM | `:30400` | `k8s/litellm/service.yaml` |
| Neo4j HTTP / Bolt | `:30085` / `:30086` | `k8s/neo4j.yaml` |
| NeoDash | `:30088` | `k8s/neodash.yaml` |
| Qdrant HTTP / gRPC | `:30083` / `:30084` | `k8s/qdrant.yaml` |
| Weaviate HTTP / gRPC | `:30087` / `:32418` | `k8s/weaviate.yaml` |
| APISIX | `:30090` | `k8s/apisix.yaml` |
| SonarQube API | `:30969` | `k8s/sonarqube/sonarqube-api-lan.yaml` |
| tool-server | `:30080` | `k8s/weyland-tool-server.yaml` |
| Woodpecker HTTP / gRPC | `:30980` / `:30900` | `k8s/woodpecker/woodpecker-{http,grpc}-lan.yaml` |

**Added 2026-10-17** (each replaced a port-forward in the docs or code):

| Service | NodePort | What gates it | Manifest |
|---|---|---|---|
| Prometheus | `:30909` | none — read-only API, admin API off | `k8s/monitoring/prometheus-lan.yaml` |
| DataHub GMS | `:30818` | `DATAHUB_GMS_TOKEN` | `k8s/data-mesh/query-lan.yaml` |
| Uptime Kuma API | `:30301` | Kuma login | `k8s/uptime-kuma/uptime-kuma-lan.yaml` |
| musicbrainz-postgres | `:30544` | password | `k8s/data-mesh/query-lan.yaml` |
| Trino | `:30843` | **rogueone only** + a Trino login over HTTPS (B233, DataGrip as `emangini`, [trino.md § Authentication](trino.md#authentication-b233-2026-10-23)) | `k8s/data-mesh/query-lan.yaml` + `netpol-trino.yaml` |
| Trino (old door) | `:30808` | **rogueone only** — plain HTTP trusts `X-Trino-User`; removed at B233 stage 3 | `k8s/data-mesh/query-lan.yaml` + `netpol-trino.yaml` |
| Valkey | `:30379` | **rogueone only** — no auth | `k8s/data-mesh/query-lan.yaml` + `netpol-valkey.yaml` |
| OpenSearch (RAG, ns `opensearch`) | `:30920` | **rogueone only** — security plugin off | `k8s/opensearch/opensearch-lan.yaml` + `netpol.yaml` |

For the older ports, the gate is in the service's runbook / query cookbook; when unsure, read its manifest.

The live list is the source of truth when this table and the cluster disagree:
```
kubectl get svc -A -o json | jq -r '.items[] | select(.spec.type=="NodePort") | "\(.metadata.namespace)/\(.metadata.name) " + ([.spec.ports[] | "\(.port)->\(.nodePort)"] | join(","))' | sort
```

## Check they answer (from rogueone)

[rogueone]
```
for p in 30909 30818 30301 30544 30808 30843 30379 30920; do if nc -z -w3 192.168.1.243 $p; then echo "$p up"; else echo "$p NOT reachable"; fi; done
```
Every line must say `up`. A rogueone-only port that refuses here means its NetworkPolicy lost the `ipBlock` or the
Service lost `externalTrafficPolicy: Local` (below).

## Watch — `lan-nodeport-watch` (B219)

Nothing used to notice a NodePort that stopped answering — the MySQL one never worked from the day it was created
(its PERMISSIVE sidecar swallowed MySQL's server-first greeting) until this watcher's first run. A user timer on
**rogueone** runs `scripts/lan_nodeport_watch.py` every 15 min. rogueone is the vantage point on purpose: the
rogueone-only ports refuse every other source, so an in-cluster blackbox probe could never test them.

- **Inventory = the live cluster** (`kubectl get svc -A`). A NodePort with no entry in `PROBES` is `UNPROBED` (exit 1),
  and an entry for a NodePort that is gone is `STALE PROBE` (exit 1) — adding or removing a NodePort means editing
  `PROBES` in the same change.
- **Protocol probes**, not TCP alone: HTTP status < 500, Redis `+PONG`, the Postgres SSL-request byte (`S`/`N`), MySQL's
  v10 greeting. A sidecar or a policy can accept the TCP handshake and still deliver nothing.
- **Parked stores** (every workload the Service selects at `replicas: 0`, `store-park.sh`) are listed, not paged.
- **Exit** 0 all up · 1 a port down / unprobed / stale probe · 2 could not check (kubectl failed, no NodePort found).
- **Alerting:** a Kuma **push** monitor `lan-nodeports` (heartbeat interval 1200 s, Telegram). Its push URL — without the
  `?status=…` query the watcher appends — is `KUMA_LAN_PUSH_URL` in `scripts/.env`; the watcher reads that ONE key from
  the file (the unit loads no EnvironmentFile: least privilege). Exit 1/2 pushes `down` with the findings; a watcher
  that stops running misses the heartbeat, which alerts too.

Run it by hand (no push):

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/lan_nodeport_watch.py --no-push
```
Expect `lan-nodeport-watch: N up, M parked, T NodePort(s) — exit 0`. Logs of the timer runs:
`journalctl --user -u lan-nodeport-watch`.

**Set up once (owner):** in Uptime Kuma (`kuma.weyland.lab`) add a **Push** monitor named `lan-nodeports`, heartbeat
interval **1200**, the Telegram notification, and put its push URL in `scripts/.env` as `KUMA_LAN_PUSH_URL=` (edit the
file yourself — never paste it into chat). Then install the timer:

[rogueone]
```
cp /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/lan-nodeport-watch.service /home/edwardmangini/IdeaProjects/weyland/nodes/rogueone/systemd/lan-nodeport-watch.timer /home/edwardmangini/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now lan-nodeport-watch.timer
```
Check: `systemctl --user list-timers lan-nodeport-watch.timer` shows a next run, and the Kuma monitor goes green after
the first one.

## Add a NodePort for a service that has none

1. **Ask first** — a NodePort puts the service on the LAN. Say what gates it (its own auth, or the policy).
2. **A `-lan` Service** next to the service's manifests (same Argo app directory): `type: NodePort`,
   `externalTrafficPolicy: Local`, the target's own pod selector, a free `nodePort` in 30000–32767 (check the live list
   above). Copy `k8s/data-mesh/query-lan.yaml`.
3. **If the target has no auth** (Trino, Valkey, OpenSearch, MLflow), its NetworkPolicy admits
   `- ipBlock: {cidr: 192.168.1.230/32}` (rogueone) on the target port and nothing else from outside the cluster.
   `externalTrafficPolicy: Local` is what makes that work: it keeps the client's source IP (single node, so no hop is
   lost), so the `ipBlock` can tell rogueone from the rest of the LAN. Pin it in `scripts/tests/write-surface-netpol.bats`
   (`ip=192.168.1.230/32` in the `pinned` list) so a widened CIDR is a deliberate, reviewed change.
4. **A meshed target** is fine with no PeerAuthentication in its namespace (PERMISSIVE accepts the plain-text NodePort
   traffic). Under STRICT (weyland-postgres) a NodePort does not work; run the work in-cluster instead.
5. **Docs:** `api.md` (the endpoint), `hosts.md` (mother's row), the table above, and the service's runbook / query
   cookbook. Then run the check above after Argo syncs.

## The guard — `scripts/check-no-port-forward.sh`

Runs in CI `repo-guards` on every pipeline (no credentials, file-only), and by hand:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-no-port-forward.sh
```
Expect `no-port-forward: OK — no port-forward commands in N file(s).` It scans every `.md`/`.sh`/`.py`/`.yaml`/
`.toml`/Dockerfile under the repo and fails (exit 1, each hit as `file:line`) on:

- a **command**: `port-forward` followed by a resource (`svc/x`, `pod/x`, `deploy/x`, …) or a port mapping
  (`9090:9090`, `"$3:$4"`) before a backtick, `)` or end of line;
- the **Python client**: a call to `kubernetes.stream`'s portforward function, or the pod-portforward connect method;
- an **instruction in prose**: the word followed by "the" or "a" (an imperative), a route word (via, over, through)
  in front of it, or IntelliJ's Forward Ports action written as a menu step after an arrow — unless negated just before
  (not, never, no, without).

Prose that names the practice to reject it passes, so the rule's own statement never trips it. **Not scanned:**
`docs/backlog.md` (DONE records describe what was), `.ipynb` (outputs are recorded data — a RAG answer quoting a
port-forward is not an instruction), generated trees, and the guard + its test. **Exit 2** = it scanned nothing (a
wrong root reads as could-not-run, never as clean). Tests: `scripts/tests/no-port-forward.bats` (11 cases). Demo:
[demos/no-port-forward.md](../demos/no-port-forward.md).

**Fixing a hit:** point the client at the service's NodePort from the table, or move the work in-cluster. No NodePort
yet? Follow "Add a NodePort" — never forward as a stopgap.
