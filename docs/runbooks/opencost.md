# B55 — OpenCost Runbook — weyland (Cloud Cost)

k8s **cost allocation** (CNCF OpenCost) for the Port **Cloud Cost** category. Bare-metal MS-A2 has no cloud
bill, so we drive it with **custom on-prem pricing**. UI at `opencost.weyland.lab`; ns `opencost`. Manifests in
`k8s/opencost/`. Part of the lab cost picture — see also the Port `cost` blueprint + Cost dashboard (B55).

---

## What it is
A single lightweight Deployment (`opencost` — cost-model + UI containers) in ns `opencost`. It **reads the
existing kube-prometheus-stack Prometheus** for resource usage and applies a pricing model to allocate cost per
namespace/workload/pod. Chart: `opencost/opencost`. Values: `k8s/opencost/opencost-values.yaml`.

## Deploy
```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart && helm repo update
helm install opencost opencost/opencost -n opencost --create-namespace -f opencost-values.yaml
# UI ingress (reuses the mkcert wildcard — copy the cert into the new ns first):
kubectl get secret weyland-wildcard-tls -n weyland -o json | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.managedFields,.metadata.ownerReferences)' | kubectl apply -n opencost -f -
kubectl apply -f opencost-ingress.yaml
```
- **Prometheus wiring is the make-or-break setting** (`opencost.prometheus.internal`): `serviceName:
  monitoring-kube-prometheus-prometheus`, `namespaceName: monitoring`, `port: 9090`. Confirm with
  `kubectl get svc -n monitoring | grep prometheus`. Healthy log line: `Success: retrieved the 'up' query against
  prometheus …`.
- **`opencost.weyland.lab` resolves via the CoreDNS wildcard**, but **rogueone needs an explicit `/etc/hosts`
  line** (`192.168.1.243 opencost.weyland.lab`) — it doesn't use CoreDNS.
- Benign at startup: `WRN Error getting LoadBalancer cost: ParseFloat … ""` — there's no cloud LB on bare metal.
- OpenCost **backfills from Prometheus history**, so real allocation numbers appear within minutes, not days.

## Custom on-prem pricing (the model)
No cloud bill → set rates in `opencost.customPricing.costModel` (chart creates the `custom-pricing-model`
ConfigMap; log line `Found configmap custom-pricing-model, watching…`). The model, from five inputs:

| input | value |
|---|---|
| MS-A2 purchase | $2,500 |
| amortization | 5 yr (60 mo) |
| avg power | ~55 W (estimate — no smart plug; 9955HX runs hotter than a U-chip) |
| electricity | $0.16/kWh (Wilmington MA = **RMLD** municipal, well under the ~$0.30 MA IOU avg; confirm on a bill) |
| box specs | 32 vCPU / 96 GB (Ryzen 9 9955HX) |

- hardware: `2500 / 60 = $41.67/mo` · power: `0.055kW × 730h × $0.16 = $6.42/mo` → **~$48.09/mo whole box**
- split 50/50 CPU:RAM over the full box → **`CPU: 0.001029`** /core/hr, **`RAM: 0.000343`** /GB/hr (and a tiny
  `storage` for the 8TB USB). OpenCost applies these to the **mother node's 8 vCPU / 32 GB** slice → k3s shows
  **~$15/mo** (its share; the other Proxmox VMs/CTs aren't k8s, so OpenCost rightly doesn't see them).

**Retune:** change any of the five inputs → recompute the three rates → `helm upgrade opencost … -f
opencost-values.yaml` (+ `kubectl rollout restart deploy/opencost -n opencost`). The formula lives in the
values-file comment.

## In Port (B50-aligned)
OpenCost is the **live detail** (per-namespace, efficiency) — linked from the Port **Launcher** (`endpoint`
entity `opencost`). Port itself holds only the **summary**: the `cost` blueprint's `weyland-infra` line (~$48/mo,
`source: opencost`) + the Cost dashboard total. We deliberately do NOT ingest granular per-namespace cost into
Port (would go stale — the thing B50 retired). The full lab cost picture (infra + Claude + LiteLLM + the deferred
subscription dump) lives in the `cost` blueprint; see `docs/backlog.md` B55.
