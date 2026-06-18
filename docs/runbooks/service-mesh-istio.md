# Istio service mesh — runbook (B8)

Istio **sidecar** mesh on mother's k3s. **Minimal profile** (istiod only — **no Istio ingress gateway;
Traefik stays the front door**). First slice meshed: **weyland-tool-server + the 4 vector/graph backends**
(qdrant, weaviate, neo4j, Postgres), **PERMISSIVE mTLS**. Design/plan: `aidlc-docs/construction/b8-istio-{design,plan}.md`.
Manifests: `nodes/mother/lab/weyland-platform/k8s/istio/`. Istio version: **1.30.1**, Kiali **v2.26**.

**Why PERMISSIVE, not STRICT (slice 1):** two un-meshed clients force it — the tool-server serves external
**NodePort** MCP clients (Hermes CT 104 + Claude Code), and the backends serve un-meshed **Dagster** (ingestion/
eval writes). STRICT would reject both. **STRICT = slice 2** (mesh Dagster, mind its egress to Ollama CT 102 +
GitHub, then flip backends STRICT).

---

## Install (on mother, `istioctl` on PATH)
```
cd ~ && curl -L https://istio.io/downloadIstio | sh - && cd istio-* && export PATH=$PWD/bin:$PATH
istioctl x precheck                                  # expect "No issues found"
istioctl install -f ~/lab/weyland-platform/k8s/istio/istio-install.yaml -y
kubectl get pods -n istio-system                     # istiod Running
istioctl version                                     # control plane version appears once istiod is up
```
`istio-install.yaml` = minimal profile + `meshConfig.extensionProviders` (the `jaeger` zipkin provider — see
Tracing). `verify-install` was **removed** in 1.30 — use `istioctl version` / pod status instead.

## Observability add-ons
- **Jaeger** (addon): `kubectl apply -f ~/istio-*/samples/addons/jaeger.yaml` (services: `tracing` = query
  UI :80/16685, `zipkin` = collector :9411).
- **Kiali**: tracked at **`k8s/istio/kiali.yaml`** (was the un-tracked addon — now committed + hardened).
  `kubectl apply -f k8s/istio/kiali.yaml`. Ingress `kiali.weyland.lab`; Jaeger ingress `jaeger.weyland.lab`
  (`k8s/istio/{kiali,jaeger}-ingress.yaml`). Both reuse `weyland-wildcard-tls` **copied into `istio-system`**:
  ```
  kubectl create secret tls weyland-wildcard-tls -n istio-system --cert=<(kubectl get secret weyland-wildcard-tls -n weyland -o jsonpath='{.data.tls\.crt}' | base64 -d) --key=<(kubectl get secret weyland-wildcard-tls -n weyland -o jsonpath='{.data.tls\.key}' | base64 -d)
  ```
  rogueone needs `192.168.1.243 kiali.weyland.lab` + `… jaeger.weyland.lab` in `/etc/hosts`.
- **Prometheus**: Kiali uses Istio's **bundled addon Prometheus** (`samples/addons/prometheus.yaml`), NOT the
  kube-prometheus-stack — a deliberate shortcut. **Consolidation + Grafana Istio dashboards = deferred
  follow-up** (see backlog B8).

## Tracing pipeline (the part that's easy to get half-wired)
Sampling alone does **nothing** — it sets *how much* to trace, not *where to send* spans. You need a
**provider** + a **Telemetry** resource:
- `istio-install.yaml` → `meshConfig.extensionProviders: [{name: jaeger, zipkin: {service: zipkin.istio-system.svc.cluster.local, port: 9411}}]`
- `k8s/istio/telemetry.yaml` → `Telemetry` with `tracing[].providers: [jaeger]`, `randomSamplingPercentage: 100`.
- **Sidecars must be restarted** to pick up the tracing bootstrap (`kubectl rollout restart deployment … -n weyland`).
- Kiali shows traces via `external_services.tracing` (gRPC `tracing.istio-system:16685`, `external_url` =
  `https://jaeger.weyland.lab`).

---

## Meshing a workload — per-pod LABEL, one at a time
The `weyland` namespace is **unlabeled**, so the per-pod **annotation does NOT inject** (the injector webhook
is namespace-scoped). Use the pod **LABEL** `sidecar.istio.io/inject: "true"` (matched by the
`object.sidecar-injector` webhook). The repo deployment manifests now carry this label.
```
kubectl patch deployment <name> -n weyland -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"true"}}}}}'
kubectl rollout status deploy/<name> -n weyland
kubectl get pods -n weyland -l app=<name>            # 2/2 = sidecar injected
curl -s http://mother:30080/status                   # no-regression: the backend still reachable (PERMISSIVE)
```
RWO/`Recreate` deployments blip briefly on restart — **do them one at a time**, validate between each.

**Rollback (un-mesh a workload):** set the label to `"false"` (the webhook only injects on `"true"`) + restart:
```
kubectl patch deployment <name> -n weyland -p '{"spec":{"template":{"metadata":{"labels":{"sidecar.istio.io/inject":"false"}}}}}'
kubectl rollout status deploy/<name> -n weyland
```

## TCP backends — the landmine (neo4j Bolt, Postgres)
Non-HTTP TCP protocols get **mis-parsed as HTTP by the inbound sidecar** → connection breaks (seen live:
neo4j `Failed to read from defunct connection … 7687`). Fix: declare the port TCP on the **Service** *before*
meshing the pod:
```
kubectl patch svc neo4j -n weyland -p '{"spec":{"ports":[{"port":7687,"appProtocol":"tcp"}]}}'
kubectl patch svc weyland-postgres -n weyland -p '{"spec":{"ports":[{"port":5432,"appProtocol":"tcp"}]}}'
```
(now in the repo Service manifests). Note: the *outbound* sidecar sniffs TCP fine — only **inbound** (the
backend's own sidecar) needed this. Validate the un-meshed Dagster→meshed-Postgres write path:
```
kubectl exec -n weyland deploy/dagster-user-code -- python3 -c "import psycopg2,os; c=psycopg2.connect(host='weyland-postgres.weyland.svc.cluster.local',port=5432,dbname='weyland',user='weyland',password=os.environ['WEYLAND_PG_PASSWORD']); cur=c.cursor(); cur.execute('SELECT count(*) FROM rag_chunks'); print(cur.fetchone()[0])"
```

## Verify mTLS + traces
- Kiali → Graph → ns `weyland`, Display → Security → **lock icons** on tool-server↔backend edges = mTLS.
- Kiali workload → **Traces** tab, or Jaeger (`jaeger.weyland.lab`) → Service `weyland-tool-server`.
- `istioctl x describe pod <pod> -n weyland` shows per-pod mTLS.

## Security (Kiali/Jaeger)
The Istio addon ships **demo-grade** defaults. Hardened in `k8s/istio/kiali.yaml`: **`view_only_mode: true`**
(read-only — anonymous users can't mutate the mesh), **ClusterRole read-only on Istio CRDs**, non-placeholder
signing key. Kiali stays `auth.strategy: anonymous` internally; **the password gate is at the ingress** (below).
**Residual (optional):** NetworkPolicy/AuthorizationPolicy + drop the remaining workload `patch` verbs.

### Ingress auth (dev-password) — `observability-auth`
Both `kiali.weyland.lab` and `jaeger.weyland.lab` were anonymous-read on the LAN. Now gated by a **Traefik
basicAuth Middleware** (`k8s/istio/observability-auth.yaml`, `traefik.io/v1alpha1`), same dev-password posture
as the other UIs. The htpasswd secret is created **out-of-band** (never committed):
```
htpasswd -nb admin weyland_dev_password | kubectl create secret generic observability-auth-secret -n istio-system --from-file=users=/dev/stdin
```
Each Ingress opts in via annotation `traefik.ingress.kubernetes.io/router.middlewares: istio-system-observability-auth@kubernetescrd`
(see `kiali-ingress.yaml` / `jaeger-ingress.yaml`). Apply:
```
kubectl apply -f k8s/istio/observability-auth.yaml -f k8s/istio/kiali-ingress.yaml -f k8s/istio/jaeger-ingress.yaml
```

## Observability — consolidated onto kube-prometheus-stack
Bring-up shortcut was Istio's **addon Prometheus** (a second Prometheus). Consolidated onto B5's
kube-prometheus-stack so there's one metrics store:
- `k8s/istio/podmonitor-istio.yaml` — the official **envoy-stats PodMonitor** + **istiod ServiceMonitor**. Both
  carry `labels: {release: monitoring}` — required to match the stack's `podMonitorSelector`/`serviceMonitorSelector`
  (without it the operator silently ignores them).
  ```
  kubectl apply -f k8s/istio/podmonitor-istio.yaml
  ```
- Verify the scrape: `count(istio_requests_total)` in Prometheus returns non-zero (was 18).
- Repoint Kiali at the stack Prometheus (`external_services.prometheus.url:
  http://monitoring-kube-prometheus-prometheus.monitoring:9090`) — edit the **repo** `k8s/istio/kiali.yaml` (never
  `kubectl edit` the live ConfigMap — see Gotchas), then push + restart:
  ```
  cp k8s/istio/kiali.yaml /tmp/kiali-addon.yaml   # then scp /tmp/kiali-addon.yaml to mother
  kubectl apply -f /tmp/kiali-addon.yaml && kubectl rollout restart deploy/kiali -n istio-system
  ```
  Then **delete the addon Prometheus** (the second one — keep B5's stack):
  ```
  kubectl delete deploy,svc,cm,sa prometheus -n istio-system
  ```
- Grafana: import Istio dashboards **into B5's Grafana** (do NOT deploy the addon Grafana) — IDs
  **7639** (mesh) / **7636** (service) / **7630** (workload) / **7645** (control-plane). They persist on the
  Grafana PVC; ConfigMap-provisioning for full IaC is an optional later step.
- Kiali also wired to Jaeger (`tracing.istio-system:16685`) and Grafana (`monitoring-grafana.monitoring:80`) via
  `external_services` — the Mesh view then shows all components green.

## STRICT mTLS (slice 2) — scope it, don't blanket it
Slice 1 is PERMISSIVE (accepts both mTLS and plaintext). STRICT *rejects* plaintext — so before flipping a
workload, **audit every client**: a STRICT target with any un-meshed (or out-of-mesh-port) client breaks that
client. In this lab the vector backends have un-meshed clients (**Prometheus app-metrics** scrapes — qdrant on
the shared `:6333`, weaviate on `:2112` — and **NodePort** admin access), so STRICT there would cost metrics +
admin for no real security gain (their actual traffic is already mTLS, both ends meshed). **Postgres is the clean
target:** in-cluster only, no metrics scrape, clients (tool-server + Dagster) all meshed.
- `k8s/istio/peerauth-postgres-strict.yaml` — `PeerAuthentication` selecting `app: weyland-postgres`, `mode: STRICT`.
  ```
  kubectl apply -f k8s/istio/peerauth-postgres-strict.yaml
  ```
- **Prove it enforces** (don't trust `nc -z` — a bare TCP connect succeeds and won't trigger mTLS rejection). From
  an **un-meshed** pod:
  ```
  kubectl run pgtest --rm -i --image=postgres:16 -n default --restart=Never -- psql "postgresql://weyland:nope@weyland-postgres.weyland.svc.cluster.local:5432/weyland?sslmode=disable" -c "select 1"
  ```
  Enforcing = **`server closed the connection unexpectedly`** (sidecar reset *pre-auth*) — NOT
  `password authentication failed` (that would mean the plaintext reached Postgres = STRICT off). Meshed clients
  keep working (tool-server `/status` → `pgvector ok`).

## Gotchas hit (don't repeat)
- **Annotation ≠ label** for injection in an unlabeled namespace (annotation is a no-op).
- **Sampling alone ships no spans** — needs the extensionProvider + Telemetry + sidecar restart.
- **TCP backends** break inbound without `appProtocol: tcp`.
- **`kubectl edit configmap kiali`** clobbered the YAML (parse error → crashloop) — edit the file + `apply`,
  don't hand-edit the live ConfigMap.
- **Addon Kiali config is untracked + insecure by default** — it's now tracked + hardened in the repo.
- **`nc -z` is a false-negative STRICT test** — a bare TCP connect succeeds; the sidecar only resets once a real
  protocol handshake starts. Test STRICT with an actual client (psql/grpc), expecting a connection reset pre-auth.
