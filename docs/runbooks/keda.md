# KEDA — runbook — ⚠️ **RETIRED 2026-08-22**

> **KEDA is no longer installed.** Both Argo Applications (`keda` 2.20.1, `keda-http-add-on` 0.15.0) were
> removed from `k8s/argocd/applications/helm-apps.yaml`; Argo pruned the workloads. The `keda` namespace was
> deleted manually. This file is kept for the gotchas below and for the reinstall recipe.
>
> **Why retired:** installed as a B43-era platform capability and never used. In 62 days it produced exactly
> ONE `ScaledObject` — the HTTP add-on's own interceptor. No `HTTPScaledObject` ever existed and nothing in the
> cluster referenced it, while it cost **10 pods / ~215 Mi / 114 operator restarts** on a node already at 93% of
> its memory reservation. The Status section below said "Installed + healthy", which describes an inert
> component as a working capability — the drift that made this easy to miss.
>
> **Its one intended consumer was the data-mesh run-mode tiering** (store sleep/wake), which is blocked on
> ceding `/spec/replicas` to an external actor via Argo `ignoreDifferences`. That carve-out was rejected on
> **mechanism, not arithmetic**: it is unscoped and permanent, so a sleeping store reports Synced/Healthy, the
> accidental-scale-to-zero safety net disappears, and the sleep state lives only in the cluster. **KEDA does not
> avoid that carve-out — it needs the identical one** (see [port-agent-easy-button.md](port-agent-easy-button.md)
> § PARKED). So KEDA was never what stood between the lab and store sleep.
>
> **The clean form of store sleep needs no KEDA at all:** commit `replicas: 0` to git and let Argo enforce it.
>
> **Reinstate** if a real trigger ever appears — the two `helm install` lines below still apply. A `ScaledJob`
> (Jobs created on a trigger) would NOT hit the Argo conflict, since Argo never manages those Job instances.

## Original runbook (B43-era platform capability)

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
