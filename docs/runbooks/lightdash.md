# Lightdash — dbt-native BI over the marts

Lightdash is the **dbt-native** BI face of the data mesh: unlike Superset (ad-hoc SQL over Trino), Lightdash builds
its dimensions + metrics **from the dbt project**, so it surfaces the tested marts (`iceberg.dbt.mart_*`) and any
`meta.metrics` declared in the dbt `schema.yml`. It runs in `data-mesh`, deployed as an **Argo multi-source Helm
app** (chart from the lightdash helm repo + values from git), the same shape as Superset. Values:
`k8s/lightdash/lightdash-values.yaml`. UI: `https://lightdash.weyland.lab`.

Design: **get it UP first with Lightdash's own login, connect the dbt project + Trino in the UI after** — exactly
how Superset defers its Trino connection. Metadata lives in the lab Postgres `lightdash` DB (bundled Postgres off);
browserless-chrome + NATS workers are off on the first cut to spare the tight mother node ([[hardware-topology]]).

## 1. Verify the chart + pin the version

The chart's value schema evolves — reconcile the value keys before deploying:

```
helm repo add lightdash https://lightdash.github.io/helm-charts
helm repo update
helm search repo lightdash/lightdash          # note the CHART version → pin it in the Argo Application (step 4)
helm show values lightdash/lightdash | less    # confirm externalDatabase / existingSecret / configMap keys
```

Reconcile any drift into `k8s/lightdash/lightdash-values.yaml` (esp. the `externalDatabase` + `existingSecret`
wiring — chart versions have moved these).

## 2. Metadata DB + role (lab Postgres)

Create the `lightdash` DB + role (same as Superset's `superset` DB). Password: use the shared dev cred
([[lab-dev-credentials]]) or a fresh one — it goes into the Secret in step 3, never inline.

```sql
CREATE ROLE lightdash LOGIN PASSWORD '<pw>';
CREATE DATABASE lightdash OWNER lightdash;
```

## 3. Secret (`lightdash-secret`, ns data-mesh)

Keys: **`postgresql-password`** (the `lightdash` PG role's password from step 2 — the chart reads the external-DB
password from this exact key, Bitnami convention, NOT `password`) and `LIGHTDASH_SECRET` (a random session key).

```
kubectl -n data-mesh create secret generic lightdash-secret \
  --from-literal=postgresql-password='weyland_dev_password' \
  --from-literal=LIGHTDASH_SECRET="$(openssl rand -hex 32)"
```

Create it directly (do NOT commit; it's the SealedSecrets/External-Secrets gap under B69). Verify the base64
round-trips clean — paste-mangling has bitten other secrets here ([[feedback-verify-secret-after-create]]).

## 4. Argo Application

Add to `k8s/argocd/applications/helm-apps.yaml` (pin `targetRevision` to the version from step 1), then push
(deploy = push; auto-sync + SSA is on):

```yaml
- apiVersion: argoproj.io/v1alpha1
  kind: Application
  metadata:
    name: lightdash
    namespace: argocd
  spec:
    project: default
    sources:
      - repoURL: https://lightdash.github.io/helm-charts
        chart: lightdash
        targetRevision: <CHART_VERSION>        # from `helm search repo lightdash/lightdash`
        helm:
          releaseName: lightdash
          valueFiles: [$values/k8s/lightdash/lightdash-values.yaml]
      - repoURL: https://github.com/edtbl76/weyland-lab.git
        targetRevision: main
        ref: values
    destination:
      server: https://kubernetes.default.svc
      namespace: data-mesh
    syncPolicy:
      automated: { selfHeal: true, prune: true }
      syncOptions: [ServerSideApply=true, CreateNamespace=false]
```

## 5. Trino auth-strip proxy (REQUIRED — Lightdash can't talk to no-auth Trino directly)

Lightdash's Trino connector **forces a password** (mandatory form field) → it sends HTTP **Basic auth**. Trino has
**no authenticator** (deliberate LAN no-auth — dbt/DataHub/Superset all connect passwordless), and Trino returns
**401 "Basic authentication is not enabled"** for ANY `Authorization` header. Enabling Trino auth would break every
other passwordless client. So Lightdash points at a tiny **nginx proxy that strips the `Authorization` header** and
forwards to Trino — Trino then sees only `X-Trino-User` (the same no-auth path dbt uses).

Manifest: `k8s/lightdash/trino-noauth-proxy.yaml` (ConfigMap + Deployment + Service `trino-noauth.data-mesh.svc`).
It's a raw manifest (not an Argo app) — `kubectl apply` it, restart the pod on any ConfigMap change.

**Two gotchas baked into it:**
- **Strip `Authorization`** (`proxy_set_header Authorization "";`) — the whole point.
- **Do NOT override `Host`.** An early `proxy_set_header Host $host` forwarded `Host: trino-noauth…`; Istio's Envoy
  routes the outbound hop by `:authority` and expects `trino.data-mesh.svc…` → mismatch → **503**. Leave Host to
  nginx's default (the proxy_pass target). (Confirmed: a direct `wget` with `Host: trino…` returns 200.)

## 6. Post-deploy — connect the dbt project + Trino (in the Lightdash UI)

1. Open `https://lightdash.weyland.lab`, complete the first-run admin onboarding (creates the org + admin user).
2. **Create project → dbt → "Manually / Pull from git repository"** (NOT the GitHub OAuth button — the self-host
   has no GitHub App configured, so OAuth dies with "bad request / missing parameter"). Then:
   - **Authorization method: Personal Access Token** (fine-grained, scoped to `edtbl76/weyland-lab`, **Contents:
     Read-only** — Metadata:Read auto-added; or a classic token with `repo`).
   - **Repository:** `edtbl76/weyland-lab` · **Branch:** `main` · **dbt version:** latest (v1.10).
   - **Project directory path:** `/nodes/mother/lab/weyland-platform/services/weyland-dagster/dbt` (leading `/` =
     from the repo root; the field defaults to `/` which is the repo root → `dbt_project.yml not found`).
3. **Warehouse connection → Trino:** host **`trino-noauth.data-mesh.svc.cluster.local`** (the proxy, NOT Trino
   directly), User `lightdash`, Password `weyland_dev_password` (throwaway — the proxy strips it), DB name `iceberg`
   (catalog), Port `8080`, SSL mode `http`, Schema `dbt`.
4. Lightdash compiles the dbt project against Trino and surfaces `mart_spotify_audio`, `mart_state_health_trends`,
   etc. as explores (only the columns declared in each mart's `schema.yml` become dimensions). Add `meta.metrics`
   to the dbt `schema.yml` later for first-class Lightdash metrics.

## Notes

- **Resource watch**: even lean (browserless + NATS off), Lightdash is ~1–1.5Gi. mother is heavily committed
  ([[feedback-clear-blockers-before-new]]) — if the pod goes `Pending` on memory, free/move something first.
- **Secret keys** the chart needs: `postgresql-password` (external-DB password, Bitnami convention — NOT `password`)
  + `LIGHTDASH_SECRET`. See step 3.
- **Superset coexists**: Superset = ad-hoc SQL exploration over any Trino catalog; Lightdash = curated dbt
  metrics/explores over the marts. Both point at the same Trino. See [[dbt-transform-tier]] + `docs/query/dbt-marts.md`.
- Auth is Lightdash's own login for now; Keycloak OIDC can be wired via its auth env later (like Grafana).
