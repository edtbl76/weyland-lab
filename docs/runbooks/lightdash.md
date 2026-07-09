# Lightdash — dbt-native BI over the marts

Lightdash is the **dbt-native** BI face of the data mesh: unlike Superset (ad-hoc SQL over Trino), Lightdash builds
its dimensions + metrics **from the dbt project**, so it surfaces the tested marts (`iceberg.dbt.mart_*`) and any
`meta.metrics` declared in the dbt `schema.yml`. It runs in `data-mesh`, deployed as an **Argo multi-source Helm
app** (chart from the lightdash helm repo + values from git), the same shape as Superset. Values:
`k8s/lightdash/lightdash-values.yaml`. UI: `https://lightdash.weyland.lab`.

**Status: DEPLOYED 2026-07-08 — chart `2.9.1` / app `0.2248.0`.** Connected to Trino via the `trino-noauth` proxy
(§5), dbt project pulled from GitHub via PAT, 44 metrics-as-code live, S3/MinIO wired, charts seeded (§7). The
step-by-step below is the reproducible bring-up.

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
  --from-literal=LIGHTDASH_SECRET="$(openssl rand -hex 32)" \
  --from-literal=S3_ACCESS_KEY='admin' \
  --from-literal=S3_SECRET_KEY='weyland_dev_password'
```

`S3_ACCESS_KEY`/`S3_SECRET_KEY` = the MinIO creds — Lightdash needs S3 (MinIO) for query-results storage +
pagination and CSV/image exports (the non-sensitive `S3_ENDPOINT`/`S3_BUCKET`/`S3_REGION`/`S3_FORCE_PATH_STYLE`
live in `lightdash-values.yaml`). **Create the `lightdash` MinIO bucket first** (`S3_BUCKET`). Create the Secret
directly (do NOT commit; SealedSecrets/External-Secrets gap under B69). Verify the base64 round-trips clean —
paste-mangling has bitten other secrets here ([[feedback-verify-secret-after-create]]).

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
        targetRevision: 2.9.1                   # app 0.2248.0 (from `helm search repo lightdash/lightdash`)
        helm:
          releaseName: lightdash
          valueFiles: [$values/nodes/mother/lab/weyland-platform/k8s/lightdash/lightdash-values.yaml]
      - repoURL: https://github.com/edtbl76/weyland-lab.git
        targetRevision: main
        ref: values
    destination:
      server: https://kubernetes.default.svc
      namespace: data-mesh
    syncPolicy:
      automated: { selfHeal: true, prune: true }
      syncOptions: [ServerSideApply=true]
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
   etc. as explores (only the columns declared in each mart's `schema.yml` become dimensions). The **44
   `meta.metrics` already declared** across the mart schemas surface as first-class Lightdash metrics on refresh.

## 7. Metrics-as-code + seed charts + content-as-code

**Metrics-as-code:** the marts' `schema.yml` carry **44 `meta.metrics`** (`meta: {metrics: {avg_x: {type:
average}}}`) — Lightdash surfaces them on a dbt refresh, version-controlled in the repo (no UI-defined metrics).
**Gotcha:** a metric name must NOT equal a column/dimension name (a `total_plays` metric on the `total_plays`
column errored ⚠ → renamed `total_plays_sum`). Lightdash field IDs are `<model>_<column-or-metric-name>`.

**Seed charts programmatically:** `scripts/lightdash_seed.py` creates 12 bar/line charts + a Music and a Health
dashboard via the REST API — no UI clicking. Mint a Lightdash personal-access-token (Settings → Personal access
tokens), then:

```
LIGHTDASH_TOKEN=<pat> python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/lightdash_seed.py
```

It auths `Authorization: ApiKey <pat>`, verifies TLS against the mkcert CA (`~/.local/share/mkcert/rootCA.pem`),
and builds cartesian charts (`chartConfig.type: cartesian` with `layout` + `eChartsConfig.series`; `flipAxes` for
horizontal-bar rankings). Requires the dbt refresh (metrics live) first, or field IDs 400.

**Content-as-code (`lightdash download`):** codify the UI/seeded charts + dashboards to YAML in the repo. From a
box that reaches `lightdash.weyland.lab` (node/npm):

```
npm install -g @lightdash/cli
NODE_EXTRA_CA_CERTS=/home/edwardmangini/.local/share/mkcert/rootCA.pem lightdash login https://lightdash.weyland.lab --token <pat>
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster/dbt && NODE_EXTRA_CA_CERTS=/home/edwardmangini/.local/share/mkcert/rootCA.pem lightdash download
```

This writes `dbt/lightdash/{charts,dashboards}/*.yml` (committed) — the reverse is `lightdash upload` (push local
YAML edits back). So charts are version-controlled + cloneable as files.

## Notes

- **Resource watch**: even lean (browserless + NATS off), Lightdash is ~1–1.5Gi. mother is heavily committed
  ([[feedback-clear-blockers-before-new]]) — if the pod goes `Pending` on memory, free/move something first.
- **Secret keys** the chart needs: `postgresql-password` (external-DB password, Bitnami convention — NOT `password`)
  + `LIGHTDASH_SECRET`. See step 3.
- **Superset coexists**: Superset = ad-hoc SQL exploration over any Trino catalog; Lightdash = curated dbt
  metrics/explores over the marts. Both point at the same Trino. See [[dbt-transform-tier]] + `docs/query/dbt-marts.md`.
- Auth is Lightdash's own login for now; Keycloak OIDC can be wired via its auth env later (like Grafana).
