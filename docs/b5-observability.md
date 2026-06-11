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

## Phase 2 (follow-on) — app metrics + alert routing
- **ServiceMonitors** for the app emitters: APISIX (prometheus plugin), CoreDNS (`:9153`),
  Traefik, Qdrant, Weaviate. May need `prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: false`.
- **Alert routing:** Alertmanager receiver → **n8n webhook → Telegram** (n8n's retained
  proactive-automation role). Wire a webhook receiver in Alertmanager config + an n8n
  workflow that forwards to Telegram.
- Optionally expose Prometheus + Alertmanager UIs via Traefik TLS too.
