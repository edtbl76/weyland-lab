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

## UI walkthrough

1. **Grafana → Dashboards → App Services** (`https://grafana.weyland.lab/d/app-services`), last row **weyland-tool-server —
   guard calls that got no answer**. Confirm the panel renders and shows **no series** (no failures). A line here means
   answers went out unguarded (`input`/`output`) or acts were refused (`act`).
2. **Grafana → Explore**, Prometheus, query `sum by (decision) (increase(guardrail_verdicts_total{validator="policy.gate"}[24h]))`.
   After the drill, `block` is at least 1.
3. **Grafana → Alerting → Alert rules**, search `GuardCallsFailing`: two rules (act critical, input/output warning), both
   **Normal**.

## Cleanup / teardown

Steps 1 and 2 create nothing. Step 3 writes two `guardrail_verdicts` rows per run (above) and launches nothing; they are
the audit trail, kept on purpose, not test data to remove. Step 4 is read-only.
