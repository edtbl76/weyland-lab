# Unleash — runbook (feature-management category, B43)

Self-hosted OSS feature flags at `unleash.weyland.lab`. The **call:** LaunchDarkly is SaaS ($, breaks $0) →
Unleash is the free self-hostable pick. **Use case** in weyland: centralize runtime toggles that today live in
env/config — guardrail mode (shadow/flag/block, B14/B35), model/RAG experiments, Hermes feature gates + kill
switches. Consumers are Python (tool-server, Hermes) → use the **Python SDK** when wiring real flags.

- Manifest: `k8s/unleash/unleash.yaml` (Deployment + Service + Ingress, Traefik TLS). **Stateless** — all state
  in Postgres, so no PVC and rolling updates are fine.
- **Meshed:** pod carries `sidecar.istio.io/inject: "true"` — STRICT-mTLS Postgres resets a non-meshed client
  (`read ECONNRESET`). `DATABASE_SSL=false` because **Istio** does the TLS, not the app. See [[postgres-strict-needs-mesh]].
- Backend store: Postgres `unleash` db owned by the `unleash` role (mirrors MLflow's pattern).
- Auth: Unleash has its **own login** (so no Traefik basicAuth middleware). Default `admin` / `unleash4all`
  (still active — change in Profile → Change password to `weyland_dev_password` when desired).
- `CHECK_VERSION=false` + `SEND_TELEMETRY=false` — LAN-only, $0, no phone-home.

## Secrets (`unleash-secret`, created out-of-band, never committed)
- `DATABASE_URL` = `postgres://unleash:weyland_dev_password@weyland-postgres.weyland.svc.cluster.local:5432/unleash`
- `INIT_ADMIN_API_TOKENS` = `*:*.weyland-unleash-admin` — admin API token (AIDLC/Claude/Hermes can create+flip flags via API)
- `INIT_BACKEND_API_TOKENS` = `*:development.weyland-flags-backend` — SDK/backend read token (deprecated alias of `INIT_CLIENT_API_TOKENS`)

## Gotchas (hit during bring-up — don't repeat)
1. **`28P01 password authentication failed` is opaque.** Postgres returns the same error whether the role is
   missing OR the password is wrong. Bisect: test creds *inside* the Postgres pod (localhost bypasses mTLS) —
   `kubectl exec -n weyland deploy/weyland-postgres -- psql "postgres://unleash:weyland_dev_password@localhost:5432/unleash" -c "SELECT 1"`.
   A `1` row proves role+password+db are fine → the fault is in the app's `DATABASE_URL` secret.
2. **Always `base64 -d` a freshly-created secret before restarting.** Root cause of the bring-up auth failure
   was a **space pasted into the secret literal** (`weyland_dev_password @weyland-postgres...`) — invisible in
   the error, only visible by decoding: `kubectl get secret unleash-secret -n weyland -o jsonpath='{.data.DATABASE_URL}' | base64 -d`.
   This is the [[feedback-oneline-commands]] copy/paste-mangling class. If the decode shows a space, retype by hand.
3. **`failed to create fsnotify watcher: too many open files`** — host inotify ceiling on mother
   (`fs.inotify.max_user_instances` was the kernel default `128`, exhausted by all the Istio sidecars). Non-fatal
   to Unleash, but bumped persistently: `/etc/sysctl.d/99-inotify-instances.conf` → `fs.inotify.max_user_instances=512`.
4. **"Connect SDK / Pending" nudge is ignorable** — a flag exists and fires webhook events with or without an SDK connected.

## Port webhook (catalog ingest)
- Port Data Source (webhook) `unleash` → blueprint `feature_flag`. Mapping `operation` must be **`create`**
  (Port rejects `upsert`). **Webhook data sources are NOT manageable over MCP** (`list_integrations` only returns
  Ocean exporters) — edit the mapping in the Port UI. The mapping JSON:
  ```json
  [{"blueprint":"feature_flag","operation":"create","filter":".body.featureName != null","entity":{"identifier":".body.featureName","title":".body.featureName","properties":{"enabled":"if .body.type == \"feature-environment-enabled\" then true else false end","project":".body.project","environment":".body.environment","createdAt":".body.createdAt","url":"\"https://unleash.weyland.lab/projects/\" + .body.project + \"/features/\" + .body.featureName"}}}]
  ```
- In Unleash: **Integrations → New → Webhook**, URL = Port ingest URL, events =
  `feature-environment-enabled` + `feature-environment-disabled` (definitive on/off state → clean `enabled`
  derivation; "created" has no env state → would null-churn). Default body (carries `featureName`/`project`/
  `environment`/`type` at top level — no custom template needed).
- **Push, event-driven:** flags appear in Port when toggled, not retroactively (fine — toggling is the tracked action).

## Deploy (first time)
```
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE ROLE unleash LOGIN PASSWORD 'weyland_dev_password'"
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE DATABASE unleash OWNER unleash"
kubectl create secret generic unleash-secret -n weyland --from-literal=DATABASE_URL='postgres://unleash:weyland_dev_password@weyland-postgres.weyland.svc.cluster.local:5432/unleash' --from-literal=INIT_ADMIN_API_TOKENS='*:*.weyland-unleash-admin' --from-literal=INIT_BACKEND_API_TOKENS='*:development.weyland-flags-backend'
kubectl get secret unleash-secret -n weyland -o jsonpath='{.data.DATABASE_URL}' | base64 -d; echo
kubectl apply -f k8s/unleash/unleash.yaml && kubectl rollout status deploy/unleash -n weyland
```
Then `unleash.weyland.lab` → login `admin`/`unleash4all` → create a flag → toggle in `development` to verify Port ingest.
