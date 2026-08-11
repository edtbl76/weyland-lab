# Langfuse — LLM observability (B103)

Self-hosted **Langfuse v3** at `langfuse.weyland.lab` (Keycloak forward-auth). Traces / scores / prompts / online
evals for every LLM call that routes through LiteLLM. Manifests: `k8s/langfuse/langfuse.yaml`; Argo app in
`k8s/argocd/applications/subdir-apps.yaml`. Memory: `b103-langfuse`.

## Architecture — reuse-first

Only the two **stateless** compute pods (`langfuse-web`, `langfuse-worker`) live in `k8s/langfuse/`. Every stateful
plane is an **existing lab service** — this is what makes it fit the single node (the old "dedicated ClickHouse won't
schedule" concern is void; the marginal cost is just the two pods):

| Plane | Reused service | Notes |
|---|---|---|
| Transactional | `weyland-postgres` (`langfuse` DB) | **STRICT mTLS** → pods are meshed (`sidecar.istio.io/inject: true`) |
| Analytical (traces/obs/scores) | `clickhouse.data-mesh` (`langfuse` DB) | **`CLICKHOUSE_CLUSTER_ENABLED=false`** (single-node) |
| Queue / cache | `valkey.data-mesh:6379` | no auth → credential-less connection string |
| Event blob store | MinIO `langfuse` bucket | `LANGFUSE_S3_EVENT_UPLOAD_*`, force-path-style |

Config split: non-secret env → ConfigMap `langfuse-config`; creds → SealedSecret `langfuse-secret`; both `envFrom`'d.
UI behind Keycloak forward-auth; **SDK ingestion uses the in-cluster Service** `http://langfuse.weyland.svc:3000` with
pk/sk keys — the mesh is PERMISSIVE except Postgres (`peerauth-postgres-strict.yaml`), so an unmeshed client reaches
the meshed web pod in plaintext, bypassing the forward-auth'd ingress. No ingestion-path exemption needed.

## First deploy

1. **Provision the backing stores** (on mother — creds pulled live, nothing hardcoded):
   ```
   kubectl -n data-mesh exec -i deploy/clickhouse -- clickhouse-client --user default --password "$(kubectl -n data-mesh get secret clickhouse-users -o jsonpath='{.data.weyland-users\.xml}' | base64 -d | grep -oP '(?<=<password>)[^<]+')" --query "CREATE DATABASE IF NOT EXISTS langfuse"
   ```
   (ClickHouse `default` password is plaintext in the `clickhouse-users` Secret's `weyland-users.xml` — **not**
   `datahub-ingestion-secrets`, whose copy is stale.)
   ```
   kubectl -n minio run mc-langfuse --rm -i --restart=Never --image=minio/mc --env="MC_HOST_m=http://$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d):$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)@minio.minio.svc:9000" --command -- mc mb -p m/langfuse
   ```
2. **Postgres role/db + mint + seal `langfuse-secret`** — one atomic block (shared `$LFPG`, so the role password and
   the secret's `DATABASE_URL` can't drift):
   ```
   LFPG="$(openssl rand -hex 24)"; kubectl -n weyland exec -i deploy/weyland-postgres -- sh -c "PGPASSWORD=\$POSTGRES_PASSWORD psql -U \${POSTGRES_USER:-postgres} -d postgres" <<< "DO \$\$ BEGIN CREATE ROLE langfuse LOGIN PASSWORD '$LFPG'; EXCEPTION WHEN duplicate_object THEN ALTER ROLE langfuse PASSWORD '$LFPG'; END \$\$; CREATE DATABASE langfuse OWNER langfuse;"; kubectl -n weyland create secret generic langfuse-secret --from-literal=DATABASE_URL="postgresql://langfuse:$LFPG@weyland-postgres:5432/langfuse" --from-literal=CLICKHOUSE_PASSWORD="$(kubectl -n data-mesh get secret clickhouse-users -o jsonpath='{.data.weyland-users\.xml}' | base64 -d | grep -oP '(?<=<password>)[^<]+')" --from-literal=LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_USER}' | base64 -d)" --from-literal=LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY="$(kubectl -n minio get secret minio-creds -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)" --from-literal=SALT="$(openssl rand -base64 32)" --from-literal=ENCRYPTION_KEY="$(openssl rand -hex 32)" --from-literal=NEXTAUTH_SECRET="$(openssl rand -base64 32)" --dry-run=client -o yaml | kubectl apply -f -
   ```
   Then adopt + seal: `kubectl -n weyland annotate secret langfuse-secret sealedsecrets.bitnami.com/managed=true --overwrite && kubectl -n weyland get secret langfuse-secret -o yaml | kubeseal --format yaml > ~/weyland__langfuse-secret.yaml`, rsync the CR into `k8s/sealed-secrets/sealed/`, push.
3. Push `k8s/langfuse/` + the Argo app; add LAN DNS `192.168.1.243 langfuse.weyland.lab`.
4. First browser hit → Keycloak → Langfuse signup; **first account = org owner**. Create the `platform` project.

## Gotchas (all hit during B103)

- **web CrashLoop = exit 134 (SIGABRT), NOT 137.** 137 = kernel cgroup OOM-kill (raise the limit); 134 = V8 aborting
  at its own heap ceiling, which V8 derives from the cgroup limit → a 768Mi limit capped the heap near ~384MB and it
  died during the boot init spike. Fix = 1536Mi limit **+ pin `NODE_OPTIONS=--max-old-space-size=1024`**.
- **Redis no-auth rejection.** `REDIS_HOST`/`REDIS_PORT` made Langfuse issue an AUTH command; password-less Valkey
  rejects it (`ERR AUTH called without any password configured`) → queue dead → worker `/api/health` 500s. Fix = a
  **credential-less connection string** `REDIS_CONNECTION_STRING=redis://valkey.data-mesh.svc:6379` (no `user:pass@`
  → no AUTH). Do **not** add a password to the shared data-mesh Valkey.
- **Worker readiness 500 = port mismatch.** The worker binds `PORT` (3000, inherited from the shared ConfigMap), not
  its 3030 default → istio's pilot-agent proxied the probe to a dead 3030 and returned HTTP 500. Align the worker's
  `containerPort` + readiness probe to **3000**.
- **ClickHouse single-node.** Without `CLICKHOUSE_CLUSTER_ENABLED=false`, migrations emit `ON CLUSTER` DDL and fail.
  `CLICKHOUSE_URL` = HTTP `:8123`, `CLICKHOUSE_MIGRATION_URL` = native `clickhouse://:9000`, `CLICKHOUSE_DB=langfuse`
  (pre-create the DB).

## LiteLLM → Langfuse emitter

`litellm_settings.callbacks: ["prometheus", "langfuse"]` in `k8s/litellm/configmap.yaml` (callbacks **stack** — metrics
+ traces both fire per request). Creds in `litellm-secrets`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_HOST=http://langfuse.weyland.svc:3000`.

- **GOTCHA — `litellm-secrets` is cherry-picked, not blanket `envFrom`.** `bifrost-provider-keys` is injected wholesale
  via `envFrom secretRef`, but `litellm-secrets` keys are named individually as explicit `env: valueFrom secretKeyRef`
  entries. Adding keys to that secret does **nothing** until you add matching `env` entries in `k8s/litellm/deployment.yaml`.
  Symptom: the callback registers, finds no host, and **silently no-ops** (no error).
- **GOTCHA — key mismatch is diagnosed in `langfuse-web` logs.** `No key found for public key` = the pk in
  `litellm-secrets` isn't in the project (wrong/mangled value) — a Postgres lookup miss, NOT a transport problem.
  A wrong host shows connection errors in LiteLLM; a mangled secret half shows "invalid credentials" *after* the pk is
  found. Rotate/re-stage keys from Project Settings → API Keys.

To set the LiteLLM keys, **source them from `scripts/.env`, never paste** (`set -a; . ./scripts/.env; set +a`). kubectl
runs in the **interactive** mother shell — non-interactive `ssh mother "kubectl…"` fails (`/etc/rancher/k3s/k3s.yaml`
is root-only and KUBECONFIG isn't loaded). Bring `.env` to mother (rsync) and run there; after any secret change,
`kubectl -n weyland rollout restart deploy/litellm` (env is read at boot; immune to the SealedSecret self-heal until
the next restart, so **push the resealed CR** or a future restart reverts).

## Verify

```
# both pods Ready
kubectl -n weyland get pods -l 'app in (langfuse-web,langfuse-worker)'
# ClickHouse schema materialized (expect ~12 tables)
kubectl -n data-mesh exec -i deploy/clickhouse -- clickhouse-client --user default --password "$(kubectl -n data-mesh get secret clickhouse-users -o jsonpath='{.data.weyland-users\.xml}' | base64 -d | grep -oP '(?<=<password>)[^<]+')" --query "SELECT count() FROM system.tables WHERE database='langfuse'"
# emitter live: fire one call through LiteLLM, then refresh the platform project → Tracing
MK="$(kubectl -n weyland get secret litellm-secrets -o jsonpath='{.data.LITELLM_MASTER_KEY}' | base64 -d)"; kubectl -n weyland run lf-trace-test --rm -i --restart=Never --image=curlimages/curl -- curl -s http://litellm.weyland.svc:4000/v1/chat/completions -H "Authorization: Bearer $MK" -H 'Content-Type: application/json' -d '{"model":"wl-default","messages":[{"role":"user","content":"trace test"}]}'
```
A trace should appear in the `platform` project within seconds. Auth failures surface as `No key found for public key`
in `langfuse-web` logs.

## Session tracking (2026-08-11)

Related traces group under one `session_id` in **Tracing → Sessions**. Keys: operator = Telegram chat_id (REST =
request_id) · agent = per-run request_id (`AgentState.session_id`) · tool-server = optional `AskRequest.session_id` ·
realm = per-dispatch uuid. Two wirings:
- **Manual-span apps** (tool-server v19 / operator v23 / agent v7): `_lf_generation` wraps each generation in
  `propagate_attributes(session_id=…, user_id=…)`.
- **Realm** (v21): langchain `CallbackHandler` + `metadata={"langfuse_session_id": <dispatch id>}`, with a contextvar
  (`obs.set_session`/`lf_config`) carrying the id through the nested delegation.

**Gotcha:** langfuse **4.x has NO `Langfuse.update_current_trace`** — it raises, gets swallowed by the fail-safe
wrapper, and silently sets nothing (traces land with no session). Use `propagate_attributes(...)`. Verify in-image:
`kubectl -n weyland exec deploy/weyland-agent -- python -c "from langfuse import Langfuse; print(hasattr(Langfuse,'update_current_trace'))"` → `False`. Demo: [demos/langfuse-sessions.md](../demos/langfuse-sessions.md).

## Evaluation (B103 — Scores · Evaluators · Datasets · Annotation)

The ONLINE eval lane, complementing the offline B84 MLflow suite; shared fixtures. Design:
`aidlc-docs/langfuse-evaluation-design.md`.

- **Judge model** = LiteLLM (one Langfuse LLM Connection → `http://litellm.weyland.svc.cluster.local:4000/v1`, master
  key). Aliases added for eval: **`wl-judge-oss`** (gpt-oss:20b, free local, the production/codified judge) and
  **`claude-haiku`** (quality lane). `k8s/litellm/configmap.yaml`.
- **Evaluators are CODIFIED, not UI.** Langfuse's eval-config API is UI/internal-only in v3.225.1 (`/api/public/eval-*`
  → 404; verified against the OpenAPI spec). So `scripts/langfuse_evaluators.py` (Dagster `registrations` asset
  `langfuse_codified_evals`) reads recent `rag-generate` generations, judges a 6-criterion catalog (relevance ·
  helpfulness · conciseness · citation · groundedness · refusal) via LiteLLM, and POSTs to `/api/public/scores`.
  Unlimited criteria, GitOps, survives a Langfuse DB reset. Add a criterion = one `CATALOG` entry. One UI evaluator
  (Relevance) is kept as the live-sampling example.
- **Datasets** — the eval-fixture SSOT is **git** (`weyland_pipeline/eval_sets/*.json`), mirrored to Langfuse Datasets
  by `scripts/langfuse_eval.py` (asset `langfuse_golden_dataset`). Langfuse holds a *copy*, never the source.
- **Human Annotation** — a `quality` score-config + a queue (UI); score-configs are API-creatable and defined by the
  evaluator script.
- **SSRF gotcha (UI evaluators only):** private-IP LLM connections are blocked; the working env var is
  `LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST` on web+worker (NOT `LANGFUSE_UNSAFE_TRUSTED_PRIVATE_IPS`, which is a no-op —
  langfuse#13097). The codified judge doesn't need it. Memory: `langfuse-session-tracking` neighbours; design doc above.

## Ops & security

- **Uptime Kuma monitor** (manual UI step — monitors are UI-managed): add `langfuse.weyland.lab` to the board.
- **Security:** UI behind Keycloak forward-auth; ingestion API reached only in-cluster (not exposed via ingress),
  authenticated by pk/sk; all creds in the SealedSecret; `TELEMETRY_ENABLED=false` (no phone-home, $0/LAN). The
  `langfuse/langfuse:3` + `langfuse-worker:3` images float on the v3 major — pin to the resolved tag once stable and
  fold into the Trivy image-scan scope.

## Remaining (in scope — part of B103, not separate backlog items)

- **Prompt federation** — Bifrost as authoring SoT → sync prompt *definitions* to Langfuse + MLflow; runtime
  trace↔prompt linkage needs Langfuse-SDK *fetch* at runtime (adopt on the highest-value agent(s) first).
- **Langfuse online evals** — Evaluators / Annotation Queues / Datasets over `platform` production traces; point
  Datasets at the B96 golden set so the offline (B84) and online eval lanes share fixtures.
