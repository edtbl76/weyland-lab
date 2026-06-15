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
scp nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml \
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
scp nodes/mother/lab/weyland-platform/k8s/monitoring/grafana-ingress.yaml \
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
scp nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml emangini@mother:~/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml
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
scp nodes/mother/lab/weyland-platform/k8s/monitoring/kube-prometheus-stack-values.yaml nodes/mother/lab/weyland-platform/k8s/monitoring/servicemonitors.yaml emangini@mother:~/lab/weyland-platform/k8s/monitoring/
scp nodes/mother/lab/weyland-platform/k8s/weaviate.yaml nodes/mother/lab/weyland-platform/k8s/apisix.yaml nodes/mother/lab/weyland-platform/k8s/coredns-lan.yaml emangini@mother:~/lab/weyland-platform/k8s/
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
