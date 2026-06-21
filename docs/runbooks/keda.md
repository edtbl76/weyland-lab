# KEDA — runbook (B43-era platform capability)

Event/HTTP-driven autoscaling, incl. **scale-to-zero**. Installed as the **run-mode tiering engine** for the data
mesh (always-on vs on-demand) and as the would-be wake-on-request layer for heavy occasional services. ns `keda`,
**not meshed** (per-workload injection; KEDA components scale meshed apps but don't carry sidecars themselves).

## Install (Helm, on mother)
```
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace
helm install http-add-on kedacore/keda-add-ons-http --namespace keda
```
- Core gives `ScaledObject` (scale on metrics/events: queue depth, cron, PromQL). **HTTP add-on** gives
  `HTTPScaledObject` + an **interceptor proxy** that holds a request while scaling the target 0→1, then forwards —
  the "click the link → it wakes" behaviour.

## Gotchas
1. **Add-on pods `Pending` on a single node = resource pressure, NOT anti-affinity.** The add-on ships 3 replicas
   each of interceptor + external-scaler; on the 16GB node they couldn't fit (node already near allocatable). The
   fix was the **32GB RAM bump** (then all replicas scheduled). Misdiagnosed it as topology at first — the tell:
   *all* replicas schedule on the *same* node once RAM frees up. Read the `FailedScheduling` event, don't assume.
2. **Cert timing on first boot:** `kedaorg-certs not found` FailedMount on metrics-apiserver/admission-webhooks is
   transient — the operator generates the cert on startup; dependents settle once it's `Running`.

## Status
Installed + healthy. **No HTTPScaledObjects in use yet** — SonarQube scale-to-zero was deliberately skipped (RAM
ample after the 32GB bump; see [[code-quality]]). Primary intended consumer: the data-mesh run-mode tiers (B1).
