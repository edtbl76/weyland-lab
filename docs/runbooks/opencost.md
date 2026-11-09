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
- split 50/50 CPU:RAM over the full box → $0.001029 per core-hour and $0.000343 per GB-hour (and a tiny `storage`
  for the 8TB USB). OpenCost applies these to the **mother node's 8 vCPU / 32 GB** slice → k3s shows **~$15/mo**
  (its share; the other Proxmox VMs/CTs aren't k8s, so OpenCost rightly doesn't see them).
- **Write the rates MONTHLY in the values file** (`CPU: 0.751406` per vCPU-month, `RAM: 0.250469` per GB-month,
  `storage: 0.000292` per GB-month). OpenCost divides the ConfigMap's values by 730 hours and keeps six decimals.
  Until B239 (2026-11-08) the hourly rates were written instead, so they became `0.000001` and `0` and every
  allocation read $0 for months.

**Retune:** change any of the five inputs → recompute the monthly rates in `k8s/opencost/opencost-values.yaml` → push
(Argo syncs the Helm app). The formula lives in the values-file comment.

## Are costs being allocated?

What OpenCost actually uses (written from the ConfigMap into the pod):

```bash
kubectl -n opencost exec deploy/opencost -c opencost -- sh -c 'grep -o "\"CPU\":\"[^\"]*\",\"spotCPU\":\"[^\"]*\",\"RAM\":\"[^\"]*\"" /tmp/custom-config/default.json'
```

Expected: `"CPU":"0.001029"…"RAM":"0.000343"` (hourly, after OpenCost's conversion). `"CPU":"0.000001"` and
`"RAM":"0"` is the hourly-written-as-monthly mistake above.

Yesterday's allocation by namespace (read-only, through the API server's service proxy, not a port-forward):

```bash
kubectl get --raw '/api/v1/namespaces/opencost/services/opencost:9003/proxy/allocation/compute?window=1d&aggregate=namespace' | python3 -c "import json,sys; a=json.load(sys.stdin)['data'][0]; [print(f'{k:20} \${v[\"totalCost\"]:.4f}') for k, v in sorted(a.items(), key=lambda kv: -kv[1]['totalCost'])[:6]]"
```

Expected: non-zero totals, `weyland` and `data-mesh` largest. All `$0.0000` means the pricing is not applied.

After a pricing change, the allocation API uses the new rates at once, but OpenCost's exported Prometheus metrics
(`node_cpu_hourly_cost`, `node_ram_hourly_cost`, which dashboards read) keep the old values until the pod restarts:
`kubectl -n opencost rollout restart deploy/opencost`. Seen 2026-11-08.

## In Port (B50-aligned)
OpenCost is the **live detail** (per-namespace, efficiency) — linked from the Port **Launcher** (`endpoint`
entity `opencost`). Port itself holds only the **summary**: the `cost` blueprint's `weyland-infra` line (~$48/mo,
`source: opencost`) + the Cost dashboard total. We deliberately do NOT ingest granular per-namespace cost into
Port (would go stale — the thing B50 retired). The full lab cost picture (infra + Claude + LiteLLM + the deferred
subscription dump) lives in the `cost` blueprint; see `docs/backlog.md` B55.
