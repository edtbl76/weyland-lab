# B5 — Observability (kube-prometheus-stack) — Deploy & Validate

Prometheus + Grafana + Alertmanager + node-exporter + kube-state-metrics via the
`kube-prometheus-stack` Helm chart, in the `monitoring` namespace. Grafana fronted by
Traefik TLS at `grafana.weyland.lab`. Values: `k8s/monitoring/kube-prometheus-stack-values.yaml`.

Commands on mother unless noted.

## Phase 1 — stack up + Grafana on TLS + cluster dashboards

### 1. Helm repo + namespace
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update prometheus-community
kubectl create namespace monitoring
```

### 2. Secrets in the monitoring namespace (NOT committed)
```bash
# Grafana admin login (pick a real password)
kubectl create secret generic grafana-admin -n monitoring \
  --from-literal=admin-user=admin \
  --from-literal=admin-password='CHANGE-ME-strong-pw'

# wildcard TLS cert for the Grafana Ingress (from ~/certs, same cert as other UIs)
cd ~/certs
kubectl create secret tls weyland-wildcard-tls -n monitoring \
  --cert=weyland-wildcard.pem --key=weyland-wildcard-key.pem
```

### 3. Install the stack
```bash
# from repo box: sync values
rsync -a nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml
# on mother: release name "monitoring" (-> service monitoring-grafana)
helm install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring -f ~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml
kubectl rollout status deploy/monitoring-grafana -n monitoring
kubectl get pods -n monitoring
```

### 4. Grafana Ingress + DNS
```bash
# from repo box:
rsync -a nodes/mother/lab/weyland-platform/k8s/monitoring/grafana-ingress.yaml \
  emangini@mother:~/lab/weyland-platform/k8s/monitoring/grafana-ingress.yaml
# on mother:
kubectl apply -f ~/lab/weyland-platform/k8s/monitoring/grafana-ingress.yaml
kubectl get ingress -n monitoring
# on rogueone: add the host to /etc/hosts (leading \n avoids gluing onto a last line
# that lacks a trailing newline; verify with getent, NOT dig)
printf '\n192.168.1.243  grafana.weyland.lab\n' | sudo tee -a /etc/hosts
getent hosts grafana.weyland.lab   # expect: 192.168.1.243  grafana.weyland.lab
```

### 5. Validate (from rogueone)
```bash
curl -sI https://grafana.weyland.lab        # expect HTTP/2 200/302, trusted cert
```
Open `https://grafana.weyland.lab`, log in (grafana-admin secret), confirm the
out-of-box dashboards have data: **Kubernetes / Compute Resources / Cluster**, **Node
Exporter / Nodes**, etc. Check `Status > Targets` in Prometheus (port-forward or via a
later Prometheus Ingress) shows the stack targets UP.

---

## Phase 2a — alert routing → Telegram (native) ✅ (2026-06-13)

**Native Alertmanager → Telegram** — chosen over Alertmanager→n8n→Telegram to keep dependencies
minimal in the failure-detection path (n8n stays standby for actions/orchestration, not delivery).
Config lives in the values file (`alertmanager.config` + `alertmanagerSpec.secrets`); the bot token
lives ONLY in a Secret (`bot_token_file`), so the values file is committable.

### 1. Bot + token Secret (NOT committed)
Bot: **Weyland Alerts** / `@weyland_alerts_bot` (via @BotFather). Chat ID: message the bot once, then
`curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message.chat.id'`.
```
kubectl create secret generic weyland-alerts-telegram -n monitoring --from-literal=bot-token='<BOT_TOKEN>'
```

### 2. Config (in the values file)
`alertmanager.config`: route → `telegram` receiver (with `Watchdog` → `null` so the always-firing
liveness alert never notifies); `telegram_configs` uses
`bot_token_file: /etc/alertmanager/secrets/weyland-alerts-telegram/bot-token` + `chat_id` +
`send_resolved`. `alertmanagerSpec.secrets: [weyland-alerts-telegram]` makes the operator mount it.

### 3. Apply — version-pinned upgrade (never bump the chart unintentionally)
```
helm list -n monitoring
rsync -a nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml emangini@mother:~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml
helm upgrade monitoring prometheus-community/kube-prometheus-stack -n monitoring -f ~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml --version <CHART_VERSION>
kubectl get pods -n monitoring | grep alertmanager
```
`<CHART_VERSION>` = the `CHART` column from `helm list` (e.g. `kube-prometheus-stack-XX.Y.Z` → `XX.Y.Z`).

### 4. Validate delivery
```
kubectl apply -f ~/lab/weyland-platform/k8s/monitoring/telegram-test-rule.yaml
kubectl delete -f ~/lab/weyland-platform/k8s/monitoring/telegram-test-rule.yaml
```
The apply fires `WeylandTelegramTest` → Weyland Alerts chat within ~1–2 min; the delete sends the
resolve (proves `send_resolved`).

## Phase 2b — app ServiceMonitors ✅ (2026-06-13)

Four app emitters now scraped via ServiceMonitors in the `weyland` namespace:
**Qdrant**, **Weaviate**, **APISIX**, **CoreDNS** (the LAN resolver). All four targets `up` in
Prometheus. Manifest: `k8s/monitoring/servicemonitors.yaml`.

**Traefik is intentionally descoped** — it's the k3s-managed, load-bearing ingress; reconfiguring it to
expose `/metrics` (entryPoint + ServiceMonitor against the kube-system service) carries real blast radius
for a metric we don't need in a lab. Revisit only if we start debugging ingress latency.

### ServiceMonitor coverage — the guard (B148, 2026-08-26)

`serviceMonitorSelectorNilUsesHelmValues: false` (below) means the operator discovers every
ServiceMonitor **regardless of label**. That solved discovery of the *monitor*; it says nothing about
whether the monitor finds anything. **`data-mesh/trino` existed for 59 days and produced zero series**
because its Service had no `metadata.labels` — a ServiceMonitor matches **Services** by their own
labels, while the `spec.selector` beside it matches **pods**. Both said `app: trino`.

The condition has **no positive signal**: `kubectl get servicemonitor` → `60d` ✅, `up{job="trino"}` →
*no data* (reads as idle), Grafana → empty panel. It can only be found by enumerating what should
exist and subtracting what does — the inverse question `check-port-iac-coverage.sh` asks of Port.

**`scripts/check-servicemonitor-coverage.sh`** reconciles every live ServiceMonitor across **three planes**:

| Plane | Source |
|---|---|
| **intended** | `.spec.replicas` on the workload the monitor selects |
| **actual** | `.status.readyReplicas` |
| **observed** | its Prometheus scrape-pool target count |

| verdict | meaning | fails? |
|---|---|---|
| `ok` | running and scraped | no |
| `blind` | **running and unmonitored** | **yes** |
| `down` | should be up and is not | **yes** |
| `sleeping` | deliberately parked (`replicas: 0` in git) | no |
| `zombie` | awake while declared parked | **yes** |
| `stale` | parked but still producing targets | **yes** |
| `orphan` | no workload **and** no targets ← trino | **yes** |
| `unmanaged` | no k8s workload declares intent, but actively scraping (kube-apiserver, kubelet) | no |

**Why reading `intended` from the cluster is legitimate here** — and normally would not be. Asking the
cluster what it intends is usually circular: it grades itself, which is how `argocd app rollback`
fools you. But **Argo `selfHeal` (75 of 78 apps; the 3 without are ConfigMap-only) continuously
overwrites `.spec.replicas` from git**, so that field stops being cluster state and becomes a cached
read of git. The mechanism that makes rollback a trap is what makes this field trustworthy. Store
sleep is deliberately *not* delegated to an external scaler for the same reason
(`k8s/argocd/applications/helm-apps.yaml:267-275`): the sleep state would then live only in the cluster.

Without the intended plane, `0 replicas` is **ambiguous input rather than an answer** — deliberately
parked and crashed-at-3am are byte-identical.

- Runs as CronJob **`servicemonitor-coverage`, 02:45 NY** (`k8s/monitoring/servicemonitor-coverage.yaml`),
  **unmeshed** — both targets (kube-apiserver, the Prometheus ClusterIP) have no sidecar, which is the
  opposite of `cron-freshness-check`, whose target *is* meshed. Read-only SA with four `list` verbs and
  no `pods/proxy`.
- **Not in CI**, and that is a trade not an oversight: `woodpecker:default` can read none of those four,
  and buying permanent cluster-wide read for a periodic lint is not worth it. The *decision logic* does
  run in CI — `scripts/tests/servicemonitor-coverage.bats`, 30 cases.
- The CronJob's embedded copy of the script is **byte-identical** to the repo file, asserted by a bats
  case. Regenerate the ConfigMap after editing the script.
- Exit **1** = the estate has a defect. Exit **2** = the guard could not do its job. Never conflate them.

```
bash scripts/check-servicemonitor-coverage.sh          # OK — 32 ServiceMonitor(s)
bash scripts/check-servicemonitor-coverage.sh --list   # every monitor + its verdict
```

### Key enabler — discover ServiceMonitors cluster-wide
By default the operator only scrapes ServiceMonitors carrying `release: monitoring`. Setting
`prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: false` (in the values file) makes it
discover **all** ServiceMonitors regardless of label — so our `k8s/monitoring/servicemonitors.yaml` needs
no release label, and any future SM is picked up automatically.

### What each emitter needed
| Emitter | Metrics endpoint | Change required |
|---------|------------------|-----------------|
| Qdrant | `:6333/metrics` (HTTP port) | none — already on `0.0.0.0`; just the SM |
| Weaviate | `:2112/metrics` | env `PROMETHEUS_MONITORING_ENABLED=true` + containerPort/service port `2112` (→ pod restart) |
| CoreDNS | `:9153/metrics` (`prometheus` plugin) | add `metrics` port `9153` to the Service + `app` label (already in Corefile) |
| APISIX | `:9091/apisix/prometheus/metrics` | service port `9091` **+ bind `export_addr.ip: 0.0.0.0`** (see gotcha) → pod restart |

> **APISIX gotcha:** the prometheus plugin defaults `export_addr.ip` to `127.0.0.1`, so metrics bind to
> loopback *inside* the pod. Prometheus scrapes the **pod IP** from another pod → `connection refused`.
> Set `plugin_attr.prometheus.export_addr.ip: 0.0.0.0` in the APISIX ConfigMap and restart APISIX.

### 1. Apply — version-pinned upgrade (values change) + manifests
```
rsync -a nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml nodes/mother/lab/weyland-platform/k8s/monitoring/servicemonitors.yaml emangini@mother:~/lab/weyland-platform/k8s/monitoring/
rsync -a nodes/mother/lab/weyland-platform/k8s/weaviate.yaml nodes/mother/lab/weyland-platform/k8s/apisix.yaml nodes/mother/lab/weyland-platform/k8s/coredns-lan.yaml emangini@mother:~/lab/weyland-platform/k8s/
helm upgrade monitoring prometheus-community/kube-prometheus-stack -n monitoring -f ~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml --version "$(helm list -n monitoring -o json | jq -r '.[]|select(.name=="monitoring").chart|sub("kube-prometheus-stack-";"")')"
kubectl apply -f ~/lab/weyland-platform/k8s/weaviate.yaml -f ~/lab/weyland-platform/k8s/apisix.yaml -f ~/lab/weyland-platform/k8s/coredns-lan.yaml
kubectl apply -f ~/lab/weyland-platform/k8s/monitoring/servicemonitors.yaml
kubectl rollout restart deployment/weyland-apisix -n weyland
kubectl rollout status deployment/weaviate -n weyland
kubectl rollout status deployment/weyland-apisix -n weyland
```

### 2. Validate — all four targets `up` (mother is headless: CLI, no browser)
```
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090 >/dev/null 2>&1 &
sleep 4; curl -s 'http://localhost:9090/api/v1/targets?state=active' | jq -r '.data.activeTargets[]|select(.scrapePool|test("weyland/"))|"\(.health)  \(.scrapePool)  \(.lastError)"'; kill %1
```
Expect four lines starting `up` for `serviceMonitor/weyland/{qdrant,weaviate,weyland-apisix,weyland-lan-dns}/0`.
A `down` line's `lastError` is the diagnosis (`connection refused` = wrong bind addr/port; `404` = wrong path).
From rogueone's browser instead: `https://grafana.weyland.lab` → Explore → `up{namespace="weyland"}`.

## Phase 3 — Grafana datasources (Jaeger + Alertmanager) + Proxmox metrics ✅ (2026-06-20)

**Surface the already-running tools INSIDE Grafana** (no new services) — provisioned datasources in the values file
under `grafana.additionalDataSources`; the datasource sidecar reloads on the version-pinned `helm upgrade`.

> **⚠️ Both Phase-3 datasources below were later REMOVED (B49, 2026-08-08).** Terminology that bites: a Grafana
> **datasource** is only a config *pointer* to a backend — deleting it **never** touches the backend pod/workload.
> Grafana provisioning is **add-only**, so dropping a datasource from `additionalDataSources` does NOT delete the live
> object; it's pruned explicitly via `grafana.deleteDatasources` (see the long note in `kube-prometheus-stack-values.yaml`).
> - **Jaeger** — retired with the trace backend in B48 (Tempo replaced it); the datasource orphaned until B49 pruned it.
> - **Alertmanager** — Grafana 13 **deprecated** the standalone `alertmanager` datasource and ships its plugin
>   **disabled** (health check → "plugin unavailable"), so B49 removed it. **GOTCHA:** kube-prometheus-stack
>   AUTO-INJECTS the AM datasource, so `deleteDatasources` alone LOSES — Grafana deletes it, the chart re-adds it in
>   the same provisioning pass. Real fix = **both** `grafana.sidecar.datasources.alertmanager.enabled: false` (stop
>   the re-add) **and** the `deleteDatasources` entry (prune the existing copy). **Alerting is unaffected** — the
>   Alertmanager StatefulSet + `Prometheus → Alertmanager → Telegram` are a separate path; view/silence alerts in
>   Alertmanager's own UI now. To run alert-ops inside Grafana later, wire the external AM via unified-alerting (not a datasource).

_Historical (2026-06-20, both since removed per the note above):_
- **Jaeger** `url: http://tracing.istio-system.svc.cluster.local:80/jaeger` — the Istio addon served the query API
  under base path **`/jaeger`**; without the suffix Grafana hit the SPA `index.html` ("invalid character '<'" on Test).
- **Alertmanager** `url: http://monitoring-kube-prometheus-alertmanager.monitoring.svc:9093`,
  `jsonData.implementation: prometheus` — firing alerts were visible in Grafana (routing always stayed Alertmanager→Telegram).

**Proxmox metrics — `prometheus-pve-exporter`** (`k8s/monitoring/pve-exporter.yaml`, ns `monitoring`, NOT meshed):
scrapes the PVE API (read-only `PVEAuditor` token `pve-exporter@pve!monitoring` in Secret `pve-exporter-secret`)
for per-node/VM/CT CPU/mem/disk. Multi-target — ServiceMonitor scrapes `/pve?target=192.168.1.232`. Grafana
dashboard import **#10347**. Token: `pveum user add pve-exporter@pve; pveum aclmod / -user pve-exporter@pve -role
PVEAuditor; pveum user token add pve-exporter@pve monitoring --privsep 0` (copy the `value` UUID — shown once).
Verify: `kubectl exec -n monitoring deploy/pve-exporter -- wget -qO- 'http://localhost:9221/pve?target=192.168.1.232' | grep pve_up`.

## Phase 4 — Loki (logs) + Tempo (traces) → unified Grafana; Jaeger retired ✅ (2026-06-21, B48)

Completes the LGTM stack. All three pillars now in Grafana (metrics + logs + traces).
- **Loki** (logs): `grafana/loki` 6.55.0, **SingleBinary**, storage → MinIO (`loki-chunks`/`loki-ruler`),
  `k8s/loki/loki-values.yaml`. Collector = **Alloy** DaemonSet (`grafana/alloy` 1.10.0, `k8s/loki/alloy-values.yaml`)
  → pushes pod logs to `loki:3100`. Grafana **Loki** datasource. View: Explore / **Logs Drilldown**.
- **Tempo** (traces): `grafana/tempo` 1.24.4, monolithic, storage → MinIO (`tempo-traces`), `k8s/tempo/tempo-values.yaml`.
  **zipkin receiver** :9411 ← Istio mesh tracing. Grafana **Tempo** datasource (:3200). View: Explore / **Traces Drilldown**.
- **Istio → Tempo:** repointed the mesh tracing provider (`istio-install.yaml` extensionProvider `tempo` →
  `tempo.monitoring.svc:9411` + `telemetry.yaml`). Apply with `istioctl install -f istio-install.yaml -y` (grab
  istioctl: `curl -sL https://istio.io/downloadIstio | ISTIO_VERSION=1.30.1 sh -`).
- **Kiali → Tempo:** `kiali.yaml` tracing `provider: tempo`, `internal_url: http://tempo.monitoring.svc:3200`, `use_grpc: false`.
- **Jaeger retired:** deleted the addon (`kubectl delete deploy,svc,sa,cm -n istio-system -l app=jaeger`) + ingress +
  the Jaeger Grafana datasource. `jaeger.weyland.lab` is gone.

### Gotchas
- **MinIO creds:** Loki/Tempo S3 creds via env from Secret `loki-minio` (copy from the working `aidlc-kb-minio-secret` —
  a wrong key → `InvalidAccessKeyId` crashloop). Loki uses the AWS-SDK env fallback; Tempo uses `config.expand-env=true`
  + `${AWS_*}`.
- **Loki SingleBinary:** `loki.commonConfig.replication_factor: 1` is mandatory (chart default 3 crashes); memberlist
  warnings are harmless.
- **Tempo "empty ring" Rate/Error panels** (FIXED B49, 2026-08-08): the metrics-generator produced 0 series. TWO
  gotchas — (1) `metricsGenerator.enabled: true` + Prometheus `enableRemoteWriteReceiver: true` enable the COMPONENT
  but NOT the processors; you also need `tempo.overrides.defaults.metrics_generator.processors: [service-graphs,
  span-metrics, local-blocks]` (grafana/tempo 1.24.4) or it generates nothing. **Verify the OUTPUT** —
  `tempo_metrics_generator_registry_active_series` > 0 and `traces_spanmetrics_*` present — NOT just the config.
- **istioctl** isn't on mother by default — download it (matching the mesh version, 1.30.1) to apply meshConfig changes.

---

## Phase 5 — App-level OpenTelemetry tracing → Tempo OTLP ✅ (2026-08-08, B49 thread b)

The Istio mesh already emits service-to-service spans (zipkin → Tempo). Phase 5 adds **app-INTERNAL** spans from the
Python services, exported OTLP → Tempo, so a trace shows what happens *inside* a request/op, not just the hop.
- **weyland-tool-server** (FastAPI): `opentelemetry-instrumentation-fastapi` + `-httpx` in `main.py::_init_otel(app)`
  → per-request spans. service.name `weyland-tool-server`.
- **weyland-dagster** (batch): `weyland_pipeline/_otel.py` — the `@traced_load` decorator on the 8 store-loaders emits
  ONE COARSE span per dataset (`<store>_load:<dataset>`, e.g. `clickhouse_load:usda_fooddata`). service.name
  `weyland-dagster` (distinct from the mesh's `dagster-user-code.weyland`). Shows which dataset/store in a hydrate is slow.
- **Wiring (both):** opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo.monitoring.svc:4318` in the k8s env (unset =
  no-op). **HTTP OTLP (:4318), NOT gRPC (:4317)** — the meshed→unmeshed hop hits an http2-framing snag over gRPC. With
  Phase-4's metrics-generator processors on, these spans also produce **span-metrics** → a RED dashboard per service.
- **Gotchas:** Dagster's multiprocess executor runs each op in a subprocess that exits when done → use
  **SimpleSpanProcessor** (Batch drops unflushed spans on exit). Do NOT auto-instrument the DB drivers — query-level
  spans explode into millions on a 17M-row hydrate; keep spans COARSE (per-op/dataset).
- **Verify:** `sum by (span_name) (traces_spanmetrics_calls_total{service="weyland-dagster"})` shows the
  `<store>_load:<dataset>` spans; `rate(tempo_receiver_accepted_spans{receiver=~".*otlp.*"}[5m])` > 0 = app spans reach Tempo.

---

## Operational reference
```
# pod status
kubectl --namespace monitoring get pods -l "release=monitoring"
# Grafana admin password — we use the grafana-admin Secret (NOT the chart default monitoring-grafana)
kubectl get secret grafana-admin -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d ; echo
# Grafana access: https://grafana.weyland.lab (Traefik TLS) — no port-forward needed
# installed chart version (pin it on every upgrade)
helm list -n monitoring
# Telegram chat id (to add another chat): message the bot, then
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[].message.chat.id'
```

---

## Known limitations (deliberate, documented)

Two things B5 intentionally does **not** cover. Both are reversible — revisit only if the need shows up.

### 1. Prometheus UI is not TLS-fronted
Only **Grafana** (`grafana.weyland.lab`) is ingressed. To reach the raw Prometheus UI (`Status > Targets`,
ad-hoc PromQL) use a port-forward:
```
kubectl -n monitoring port-forward svc/monitoring-kube-prometheus-prometheus 9090:9090
```
Day-to-day this is fine — Grafana is the dashboard view and covers status checks. If a browsable Prometheus
is ever wanted, add a Traefik Ingress mirroring `grafana-ingress.yaml`.

### 2. Traefik metrics are descoped
The ingress controller is **not** scraped. This is a risk/value call specific to k3s, not an oversight:
- **Riskiest change path.** Traefik is deployed by the k3s `helm-controller`, not a manifest we own —
  `kubectl edit` gets reverted on reconcile. The supported route is a `HelmChartConfig` in
  `/var/lib/rancher/k3s/server/manifests/` on the mother node (enable `metrics.prometheus` + a metrics
  entrypoint/port). A bad value can wedge the helm-controller mid-reconcile.
- **Highest blast radius.** Every `*.weyland.lab` UI (Grafana, Dagster, n8n, chat, Headlamp, Filestash,
  APISIX dashboard) rides Traefik. A failed reconcile takes them **all** down at once — including the
  Grafana you'd use to notice. The four data-plane emitters each fail in isolation.
- **Low marginal value, partly redundant.** Ingress request/latency metrics are nice-to-have at lab scale;
  **APISIX already provides gateway-layer request telemetry** (same kind of signal). What we'd actually
  alert on (node/mem/disk, pod restarts, a DB down) is fully covered by Phase 1 + the four emitters.

**To add it later:** drop a `HelmChartConfig` overriding the k3s Traefik chart values, then a ServiceMonitor
selecting the `traefik` service in `kube-system`. Validate the values before letting the helm-controller
reconcile (it's the front door for every UI).

## Phase 5 — log alerts via the Loki ruler (B51) ✅ (2026-06-21)

Alert on **log patterns** (not just metrics) by enabling Loki's **ruler** → the **same Alertmanager → Telegram**
pipeline as Phase 2a. One alert system for metrics + logs (shared routing/silencing/grouping); no second
alerting stack. Chosen over Grafana-managed alerts precisely to keep one pipeline.

### 1. Ruler config + rules mount (in `k8s/loki/loki-values.yaml`)
- `loki.rulerConfig`: `storage.type: local` + `storage.local.directory: /rules`, `rule_path: /tmp/loki-rules`,
  `alertmanager_url: http://monitoring-kube-prometheus-alertmanager.monitoring.svc.cluster.local:9093`,
  `enable_alertmanager_v2: true`.
- `singleBinary.extraVolumes`/`extraVolumeMounts`: mount the `loki-rules` ConfigMap at **`/rules/fake`** — the
  single-tenant dir the ruler scans (`auth_enabled: false` → tenant literally `fake`). The chart's own
  rules-sidecar path in SingleBinary is fiddly; mounting our own ConfigMap is deterministic.

### 2. Rules (in `k8s/loki/loki-rules-configmap.yaml`)
Prometheus-style alerting rules with **LogQL** exprs, e.g. `WeylandErrorLogSpike`:
`sum(count_over_time({namespace="weyland"} |~ ` + "`(?i)(error|exception|traceback)`" + ` [5m])) > 100`.
Threshold is a tunable noise floor (a busy debug session hit ~114 — start at 100, adjust to your baseline).

### 3. Apply
```bash
kubectl apply -f ~/lab/weyland-platform/k8s/loki/loki-rules-configmap.yaml
helm upgrade loki grafana/loki -n monitoring -f ~/lab/weyland-platform/k8s/loki/loki-values.yaml --version 6.55.0
kubectl rollout restart statefulset/loki -n monitoring     # forces an immediate rule reload
```

### 4. Validate
`kubectl logs -n monitoring loki-0 -c loki | grep -iE 'ruler|rule file|alertmanager'` → expect
`ruler up and running` + `updating rule file file=/tmp/loki-rules/fake/<file>` + the query executing. A firing
rule reaches the **Weyland Alerts** Telegram chat (same receiver as metric alerts); it auto-**resolves** when
the count falls back under threshold (a resolved ping confirms the resolution path too). Add rules under
`groups:` → re-apply + restart.
