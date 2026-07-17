# OPA Gatekeeper — admission-control policy (B1.6 L5 Slice B)

**What:** Gatekeeper is policy-as-code for the **cluster control plane** — an admission webhook that evaluates
every create/update against OPA/Rego constraints. It's the complement to Ranger's data-plane authz: Ranger governs
*queries* on Trino, Gatekeeper governs *what gets admitted* to the cluster. Slice B of the L5 (Governance/Security)
layer (Ranger + OPA + Soda). All constraints currently run in **dryrun** — they audit, they don't block.

**Where:**
- UI (Policy Manager): **https://gatekeeper.weyland.lab** (Keycloak forward-auth, like Ranger). Read-only
  violation triage.
- Grafana: **OPA Gatekeeper** dashboard (uid `gatekeeper-l5`) — trend/health view.
- Manifests: `k8s/gatekeeper/` — `gatekeeper-values.yaml` (Helm chart via Argo) · `constraints.yaml` (the
  policies) · `policy-manager.yaml` (the UI) · `metrics.yaml` (Prometheus) · `dashboard.yaml` (Grafana).
- ns `gatekeeper-system`.

## Architecture

Helm chart (Argo app), trimmed for the tight node: `replicas: 1` on both controller-manager and audit,
`disableMutation: true` (validation only — keeps the mutating webhook out of the admission path), `auditInterval: 300`
(re-audit every 5 min; the 60s default is chatty). The `postInstall.labelNamespace` hook is kept **enabled** — it
stamps `kube-system` + `gatekeeper-system` with `admission.gatekeeper.sh/ignore` so Gatekeeper never validates (and
can't deadlock) its own or the API's namespaces.

Each policy is a **ConstraintTemplate** (defines a `kind` + the Rego) plus a **Constraint** (an instance of that
kind that sets `enforcementAction` + `match`). Apply `constraints.yaml` **after** the chart has established its CRDs.

## The three constraints (all `enforcementAction: dryrun`)

| Constraint | Kind | Rule | Scope |
|---|---|---|---|
| `ns-must-have-owner` | `K8sRequiredLabels` | Namespaces must carry an `owner` label | Namespaces (infra ns excluded: kube-system/public/node-lease, default, gatekeeper-system, istio-system, argocd) |
| `no-latest-images` | `K8sNoLatestTag` | Pods can't use `:latest` or an untagged image — pin a version | Pods (excl. kube-system, gatekeeper-system) |
| `require-mem-limits` | `K8sRequireMemLimit` | Every container must set a memory limit (unbounded pods OOM the node) | Pods in `data-mesh`, `weyland` |

**dryrun vs enforce.** `dryrun` records violations in the constraint's `status` (and in metrics + the UI) but
admits everything — nothing is blocked. Review the audit, then flip the safe ones to `enforcementAction: deny` in
`constraints.yaml` and re-apply to start rejecting new violations at admission. (`no-latest` is the natural first
one to enforce; several lab apps deliberately run `:latest` — e.g. Cube bundles Cube Store on `:latest` — so audit
before flipping, [cube.md](cube.md).)

## Policy Manager (the Report UI)

`quay.io/sighup/gatekeeper-policy-manager:v1.1.1`, ns `gatekeeper-system`, read-only. It reads Gatekeeper's own CRDs
(ConstraintTemplates + Rego, Constraints + `status.violations`, Config) and renders a browsable **Report** of every
violation — the per-resource "which pod violates what" view (the UI version of the `kubectl` violation dumps).
Runs under a read-only ClusterRole; `gatekeeper-system` enforces PodSecurity `restricted` so the pod sets
`runAsNonRoot` + drops all caps. Ingress chains **local** middleware copies (`redirect-https` + `traefik-forward-auth`)
because Traefik blocks cross-ns middleware refs; `GPM_PREFERRED_URL_SCHEME=https` avoids the Ranger-style downgrade.

## Grafana dashboard + metrics

`dashboard.yaml` is a ConfigMap in the `monitoring` ns labeled `grafana_dashboard: "1"` → the kube-prometheus-stack
Grafana sidecar auto-imports it. Panels: total violations, constraints, templates, audit duration, violations by
enforcement action, webhook request rate. Metrics come from `metrics.yaml`: the chart ships no metrics Service, so a
**headless** Service fronts both pods (`gatekeeper.sh/system: "yes"`) on `:8888` and a ServiceMonitor scrapes each
(auto-discovered — no release label). **Note:** `gatekeeper_violations` is aggregate (by `enforcement_action`) — for
per-resource drill-down use the Policy Manager, not Grafana.

## Adding a constraint

1. In `constraints.yaml`, add a **ConstraintTemplate** (a `kind` under `templates.gatekeeper.sh/v1` + the Rego
   `violation` rule) and a **Constraint** instance (set `enforcementAction: dryrun`, a `match` on kinds/namespaces).
2. Apply (on **mother**), start in dryrun, and check what it catches:
   ```
   kubectl apply -f ~/constraints.yaml
   kubectl get constrainttemplates
   kubectl get k8srequiredlabels,k8snolatesttag,k8srequirememlimit
   kubectl get k8snolatesttag no-latest-images -o jsonpath='{.status.totalViolations}{"\n"}'
   kubectl get k8snolatesttag no-latest-images -o yaml   # → status.violations, the per-resource list
   ```
3. Once the audit is clean/understood, flip `enforcementAction: deny` and re-apply.

## Gotchas

- **Apply constraints only after the chart's CRDs exist** (ConstraintTemplate + the generated constraint kinds) —
  else the apply fails on unknown kinds.
- **Keep the `labelNamespace` post-install hook enabled** — it's what stops Gatekeeper deadlocking its own / the
  API's namespaces.
- **Don't remove the infra `excludedNamespaces`** — demanding an `owner` label or a mem-limit on kube-system pods
  would flood the audit (and, under `deny`, could wedge the cluster).
- **Grafana can't do per-resource** — that's the Policy Manager's job.

## Links
- [ranger.md](ranger.md) · [soda.md](soda.md) · [observability.md](observability.md) ·
  [argocd.md](argocd.md) · [keycloak.md](keycloak.md)
