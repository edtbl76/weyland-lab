# Demo — The act guard, enforced (B207)

The tool-server's three act endpoints (`/pipeline/trigger`, `/evals/run`, `/evals/score`) launch Dagster jobs. Who may
launch them is decided by `policy.gate` in weyland-guard (allowlist `weyland-operator: *`, 30/min, mode `block`). Until
2026-10-13 that decision was recorded and then **ignored**: the endpoints called the guard and discarded its answer, so a
refused act launched anyway. This demo proves the enforcement point, not the decision: a refused act gets `403` and
nothing launches.

Four layers, each shown failing the way it should:

| Layer | Refuses | Where |
|---|---|---|
| Mesh, act paths | any caller that isn't the MCP gateway's identity | `k8s/istio/authz-toolserver-act.yaml` |
| Mesh, `/guard/act` | any caller that isn't the tool-server's identity | `k8s/istio/authz-guard-act.yaml` |
| App, encoded slashes | a path with `%2F`/`%5C` (Istio matches the raw path, uvicorn decodes it) | tool-server + guard middleware |
| App, the verdict | an actor `policy.gate` refuses, or a guard that can't answer | `_guard_act` in the tool-server |

Sequence diagram: [../diagrams/flow-act-tool.md](../diagrams/flow-act-tool.md). Runbooks:
[../runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md) § Anti-spoof, [../runbooks/guardrails.md](../runbooks/guardrails.md).

## CLI walkthrough (run 2026-10-14 against the live cluster)

`kubectl` works from rogueone or mother.

**1. A direct act from the LAN is refused by the mesh** (not the gateway's identity):

```
curl -s -w ' %{http_code}\n' -X POST http://mother:30080/pipeline/trigger -H 'Content-Type: application/json' -d '{"job_name":"weyland_ingestion_job"}'
```
Observed: `RBAC: access denied 403`. Compare `curl -s http://mother:30080/health` → `200`: the port is open, the act path is not.

**2. Only the tool-server may ask the guard about an act.** From any other pod, even claiming to be the operator:

```
kubectl -n weyland exec deploy/weyland-agent -c weyland-agent -- python -c "import urllib.request as u,urllib.error as e,json
r=u.Request('http://weyland-guard.weyland.svc.cluster.local:8080/guard/act',data=json.dumps({'request_id':'demo-act','tool':'pipeline/trigger','actor':'weyland-operator'}).encode(),headers={'Content-Type':'application/json'})
try: x=u.urlopen(r,timeout=10); print(x.status, x.read()[:120])
except e.HTTPError as x: print(x.code, x.read()[:120])"
```
Observed: `403 b'RBAC: access denied'`. CI asserts the same on every run (`scripts/integration/guard-blackbox.sh` step 5).

**3. The tool-server enforces the verdict.** From inside the tool-server pod (localhost is past the mesh, so this isolates
the app's own enforcement), act as an actor that is not on the allowlist, then try the encoded-slash bypass:

```
kubectl -n weyland exec deploy/weyland-tool-server -c weyland-tool-server -- python -c $'import urllib.request as u, urllib.error as e, json\ndef call(m, p, h=None, b=None):\n    r = u.Request("http://localhost:8080" + p, data=b, method=m, headers=h or {})\n    try:\n        x = u.urlopen(r, timeout=30); print(p, x.status, x.read()[:300].decode())\n    except e.HTTPError as x:\n        print(p, x.code, x.read()[:300].decode())\ncall("POST", "/pipeline/trigger", {"Content-Type": "application/json", "X-Forwarded-Consumer": "b207-drill-not-allowlisted"}, json.dumps({"job_name": "weyland_ingestion_job"}).encode())\ncall("GET", "/pipeline%2Ftrigger")\n'
```
Observed (tool-server log): `"POST /pipeline/trigger HTTP/1.1" 403 Forbidden` and `"GET /pipeline/trigger HTTP/1.1" 400 Bad
Request`. The `403` body is `blocked by policy.gate: actor 'b207-drill-not-allowlisted' not in the act allowlist`; the
`400` body is `encoded path separators are not accepted`. It uses the routine `weyland_ingestion_job` on purpose: the
request model rejects unknown job names (422) before the guard is asked, so even a broken guard costs one routine run.

**4. The decision and the refusal are both on record:**

```
kubectl exec -i -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT created_at, actor, validator, decision, left(reason,60) AS reason FROM guardrail_verdicts WHERE hook='act' AND actor='b207-drill-not-allowlisted' ORDER BY created_at DESC LIMIT 4;"
```
Observed:
```
 2026-10-14 04:12:01.489802+00 | b207-drill-not-allowlisted | policy.audit | pass  | pipeline/trigger {'job_name': 'weyland_ingestion_job'}
 2026-10-14 04:12:01.476165+00 | b207-drill-not-allowlisted | policy.gate  | block | actor 'b207-drill-not-allowlisted' not in the act allowlist
```
Before B207 the same two rows were written and the job launched. The rows prove the decision; step 3's `403` proves
the enforcement.

**Not shown live: a guard outage.** With the guard unreachable an act is refused (`blocked by guard-unavailable: guard
unavailable (connection): action refused`) and `tool_server_guard_failures_total{hook="act"}` rises, firing the critical
`GuardCallsFailing`. Covered by `services/weyland-tool-server/tests/test_main.py` (the act fails closed, the failure is
counted); taking the shared guard down to show it would leave every caller unguarded for the duration.

## Write surfaces (B209), run 2026-10-14

The act guard covers three endpoints. B209 put front doors on the other surfaces that took writes from any pod.
Sequence: [../diagrams/flow-write-surfaces.md](../diagrams/flow-write-surfaces.md).

**5. Refused from a pod no policy admits** (`weyland-guard`):
```
kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import httpx; print(httpx.post('http://dagster-webserver.weyland.svc.cluster.local:3000/graphql', json={'query':'{version}'}, timeout=6).status_code)"
```
Observed: `503`, `server: envoy`, in 0.1 s: "upstream connect error … remote connection failure". The same from that pod
to `realm-of-agents:8080/agents` (0.1 s), `store-scaler.data-mesh/healthz` (2.2 s, unmeshed target) and
`a2a-inspector:8080` (2.2 s).

**6. Admitted for the real callers:** from `dagster-user-code`, Dagster `{version}` → `200` and Realm `/agents` → `200`;
from the operator, Realm `/agents` → `200`; from `port-agent`, store-scaler `/healthz` → `200`. Prometheus still
scrapes the Realm (`up=1`). Signed in, https://dagster.weyland.lab and https://realm.weyland.lab both load (owner,
2026-10-14).

**7. The Realm asks for a login, and is free by default:**
```
curl -sk -o /dev/null -w '%{http_code}\n' https://realm.weyland.lab/agents
```
Observed: `307` (to Keycloak). A default `/route` from `dagster-user-code` ran on `wl-judge`, the free local lane
(Realm log: `Gná · dispatch — thinking (wl-judge)`), answering in 2.1 s.

**8. The Realm holds no write tool:** its loader reports `loaded 146 VK tools from Bifrost` on the `agents-read` key,
none write-shaped (no Playwright, Linear, GitHub or memory writes).

**9. The guard:**
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-write-surfaces.sh
```
Observed: `OK — 61 deployed service(s): 40 take writes, each with a policy, a front door or a tracked gap (11 gap(s));
21 read-only.` The 11 gaps are B211's, printed every run. Negative case: `scripts/tests/write-surfaces.bats` shows an
undeclared `writes`, an open surface and a gap with no backlog item each failing with exit 1, named.

**Observed failing against the real tree (RUN 2026-10-21):** the real registry with one open writer appended (a copy;
the repo is untouched):
```
A=/home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/applications.yaml; T=$(mktemp); sed '/^excluded:/i\  - {key: demo-open-writer, deployed: true, writes: true, metrics: false, ingress: false, name: Demo Open Writer, group: ai-serving}' "$A" > "$T"; REGISTRY_FILE="$T" bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-write-surfaces.sh; echo "exit=$?"; rm -f "$T"
```
`WRITE SURFACES WITHOUT A FRONT DOOR: demo-open-writer: takes writes and has no front door — add a
NetworkPolicy/AuthorizationPolicy selecting app=demo-open-writer, a front_door: reason, or a tracked accepted_gap`,
`exit=1`. The unmodified run is `OK — 61 deployed service(s): 40 take writes … (0 gap(s)); 21 read-only.`

**Not shown live: the Telegram sender check and the sweep's redaction.** A stranger's "yes" needs a second Telegram
account in an allowed group, and a redaction needs a secret in a firing alert's logs. Both are pinned by tests:
`services/weyland-operator/tests/test_ingress.py` (8 cases: a stranger in an allowed group, a missing sender, an anonymous
admin, a spoofed chat id) and `tests/test_incidents.py` (token shapes, URL passwords, `key=value` secrets, a private-key
block, and a redaction failure that drops the message). The owner's own chat keeps working: their entry is a private
chat, whose id is their user id.

## The rest of the write surfaces (B211), run 2026-10-14

B209's guard found 11 more services that took writes from any pod, and the stores behind them had none either. Each now
has a front door. Runbook: [../runbooks/write-surfaces.md](../runbooks/write-surfaces.md).

**10. Refused from a pod no policy admits** (`weyland-guard`). For meshed targets the refusal is an instant envoy `503`;
for raw-TCP stores the connection resets. Observed: Trino, the Trino no-auth proxy, Nessie, MLflow, Feast, OpenSearch,
the operator, promptfoo, the Flink REST API, APISIX's etcd and buildkitd all refused. The stores, probed at the protocol
level (a Kafka `ApiVersions`, a Redis `PING`, an HTTP `GET`), so a sidecar accepting the TCP handshake doesn't read as
open:
```
kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- python - redpanda.data-mesh.svc.cluster.local:9092 valkey.data-mesh.svc.cluster.local:6379 opensearch-cluster-master.data-mesh.svc.cluster.local:9200 glitchtip-valkey.weyland.svc.cluster.local:6379 registry.weyland.svc.cluster.local:5000 < /home/edwardmangini/IdeaProjects/weyland/scripts/probe-store.py
```
Observed: Redpanda, Valkey and GlitchTip's Valkey reset; DataHub's OpenSearch and the registry `503`.

**11. Admitted for the real callers**, each on a fresh connection (a policy doesn't cut a connection that was already
open, so a long-lived client proves nothing):
- `dagster-user-code` reaches all of the above, plus Redpanda (`ApiVersions` answered) and Valkey (`+PONG`); a Trino
  `SHOW SCHEMAS FROM iceberg` returned 9 schemas. Flink's JobManager reaches Nessie, Cube reaches the no-auth proxy,
  `rag-index-opensearch` reaches OpenSearch, and APISIX reaches etcd. rogueone and `ray-head` reach MLflow's NodePort.
- Redpanda: Kafka Connect, Flink's TaskManager, `rag-index-opensearch` and `rag-index-neo4j`. Connect's `musicbrainz-cdc`
  stayed `RUNNING`, and both Flink session jobs (`cdc-demo-live`, `health-state-risk`) stayed `RUNNING`/`STABLE`. CI's
  `test-integration-datahub` step (`rpk topic list`) was refused on CI #363, the one caller the mesh metrics couldn't
  show, and is now admitted by step name.
- Valkey: `feast-server`, Superset and Langfuse (`+PONG`). Superset is refused by Redpanda, which it never uses.
- GlitchTip's Valkey: `glitchtip-web` and `glitchtip-worker` (`+PONG`); both are refused by the shared Valkey.
- DataHub GMS → its OpenSearch: `_cluster/health` `200`. registry-ui → the registry: the catalog lists.
- Prometheus still scrapes the meshed ones (Valkey and GMS envoys `up=1`).

**12. The registry: pulls open, pushes authenticated.**
```
curl -sk -o /dev/null -w 'pull GET %{http_code}\n' https://registry.weyland.lab/v2/ && curl -sk -o /dev/null -w 'pull POST %{http_code}\n' -X POST https://registry.weyland.lab/v2/x/blobs/uploads/ && curl -sk -o /dev/null -w 'push host %{http_code}\n' https://registry-push.weyland.lab/v2/
```
Observed: `pull GET 200`, `pull POST 404` (Traefik has no route for a write on the pull name, over HTTP or HTTPS), `push
host 401`; the push host over plain HTTP `404`. With credentials the push host answers `200`, and CI #361 pushed its
images, build cache and cosign signatures through it.

**13. The operator's `/operator/ask` is free by default.** A question with no `allow_paid` answered in 2.7 s ("19
Kubernetes namespaces"), and `operator_brain_selected_total{brain="local"}` counted it, with no paid brain selected.

**14. The guard:** `check-write-surfaces.sh` → `OK — 61 deployed service(s): 40 take writes, each with a policy, a front
door or a tracked gap (0 gap(s)); 21 read-only.` Ollama, on rogueone, counts as a front door: ufw admits only mother and
the local Docker bridge on 11434.

## GuardCallsFailing: the alert can fire and reaches Telegram (run 2026-10-21)

The DoD re-audit found live `/metrics` exporting no `tool_server_guard_failures_total` series, so the first act failure
would have created its series at 1, which `increase()` never sees. Since `git-5fdadd70` every hook × cause series
exists at 0. Three proofs:

1. **The rule fires on the first failure** (CI, every build): `scripts/tests/fixtures/alert-rules/guard-failures.test.yaml`
   via `scripts/tests/alert-rules.bats`. A series at 0 that goes to 1 pages critical. The same failure on a series born
   at 1 stays silent, which is the bug this fix closes.
2. **The series exist live:**
   ```
   curl -s 'http://192.168.1.243:30909/api/v1/query' --data-urlencode 'query=count(tool_server_guard_failures_total)'
   ```
   Expected `9` (3 hooks × 3 causes), all at 0 while the guard is healthy.
3. **Delivery drill** (labelled `drill=true`, expires in 2 min; the alert's real labels, so it routes like the page):
   ```
   kubectl -n weyland exec deploy/weyland-guard -c weyland-guard -- python -c "import json,datetime as dt,urllib.request; n=dt.datetime.now(dt.timezone.utc); a=[{'labels':{'alertname':'GuardCallsFailing','severity':'critical','hook':'act','cause':'timeout','job':'weyland-tool-server','namespace':'weyland','drill':'true'},'annotations':{'summary':'DRILL — GuardCallsFailing act (delivery test; nothing is wrong)'},'startsAt':n.isoformat(),'endsAt':(n+dt.timedelta(minutes=2)).isoformat()}]; print(urllib.request.urlopen(urllib.request.Request('http://monitoring-kube-prometheus-alertmanager.monitoring.svc.cluster.local:9093/api/v2/alerts',data=json.dumps(a).encode(),headers={'content-type':'application/json'},method='POST'),timeout=10).status)"
   ```
   Pass = `200`, then `alertmanager_notifications_total{integration="telegram"}` +1 and `…_failed_total` unchanged.
   **Run 2026-10-21 16:44 UTC:** `200`; 13,915 → 13,916 at 16:45:48, failed 17 → 17.

## UI walkthrough

1. **Grafana → Dashboards → App Services** (`https://grafana.weyland.lab/d/app-services`), last row **weyland-tool-server —
   guard calls that got no answer**. Confirm the panel renders and shows **no series** (no failures). A line here means
   answers went out unguarded (`input`/`output`) or acts were refused (`act`).
2. **Grafana → Explore**, Prometheus, query `sum by (decision) (increase(guardrail_verdicts_total{validator="policy.gate"}[24h]))`.
   After the drill, `block` is at least 1.
3. **Grafana → Alerting → Alert rules**, search `GuardCallsFailing`: two rules (act critical, input/output warning), both
   **Normal**.

## Cleanup / teardown

Steps 1, 2 and 5 to 9 create nothing (step 7's `/route` writes only its MLflow and Langfuse traces). Step 3 writes two `guardrail_verdicts` rows per run (above) and launches nothing; they are
the audit trail, kept on purpose, not test data to remove. Step 4 is read-only.

Steps 10 to 14 (B211) create nothing either: 10 and 11 are reads and protocol probes over fresh connections (a Kafka
`ApiVersions`, a Redis `PING`, an HTTP `GET`, a Trino `SHOW SCHEMAS`); 12 is a `GET`, an unauthenticated `POST` the
route refuses, and a `401`; 13 is one read-only operator question; 14 reads the repo. The step-9 negative case writes
one temp copy of `applications.yaml`, deleted by the same command. Nothing to tear down.