# Superset — BI / SQL Exploration Layer (B65)

**What:** Apache Superset 6.1.0 — browser-based BI, SQL Lab, dashboards, and chart exploration over the query layer (Trino primary). Deployed via Helm (`apache/superset` 0.17.2) in ns `data-mesh`. UI at `superset.weyland.lab`.

**Auth:** Keycloak OIDC (`superset` client, `weyland` realm). Fallback local admin: `admin` / `weyland_dev_password` (break-glass only). `emangini` gets Admin role on first OIDC login (`AUTH_USER_REGISTRATION_ROLE=Admin`).

**Celery worker parked by default (B199, 2026-10-01):** `superset-worker` runs at `replicas: 0`. Nothing needs it today
(no async queries or reports are configured, `superset-values.yaml`); wake it with `scripts/store-park.sh up
superset-worker` (one command: commit, push, wait) before turning either on.

**Cache / Celery:** shared Valkey (`valkey.data-mesh.svc:6379`, `k8s/data-mesh/valkey.yaml`) — BSD Redis fork, no persistence, ephemeral cache only.

**Metadata DB:** lab Postgres (`weyland-postgres.weyland.svc:5432`, db `superset`, user `superset`).

---

## Connect / Access

- **UI:** `https://superset.weyland.lab` — sign in with Keycloak
- **SQL Lab:** top nav → SQL → SQL Lab; pick a database, schema, table
- **Trino:** database `Trino`, URI `trino://superset@trino.data-mesh.svc.cluster.local:8443/iceberg` with the
  `superset` login (B233, HTTPS + password; the connection is stored in Superset's DB, set in its UI —
  [trino.md § Authentication](trino.md#authentication-b233-2026-10-23) step 8)
- **Postgres DBs:** each lab DB is a separate Superset database connection (weyland, dagster, datahub, glitchtip, keycloak, lakefs, mlflow, nessie, sonarqube, superset, unleash)

---

## Deploy

GitOps: `k8s/superset/superset-values.yaml` + Argo Application in `k8s/argocd/applications/helm-apps.yaml`. Push → Argo syncs → Helm deploys.

**Imperative secrets (not in git — must recreate after cluster rebuild):**
```
kubectl -n data-mesh create secret generic superset-env --from-literal=SUPERSET_SECRET_KEY=$(openssl rand -base64 42) --from-literal=DB_PASS=weyland_dev_password --from-literal=OIDC_CLIENT_SECRET=<from tofu output superset_client_secret>
```

**Postgres DB + user (one-time):**
```
kubectl -n weyland exec deploy/weyland-postgres -- env PGPASSWORD=weyland_dev_password psql -U weyland -c "CREATE USER superset WITH PASSWORD 'weyland_dev_password';"
kubectl -n weyland exec deploy/weyland-postgres -- env PGPASSWORD=weyland_dev_password psql -U weyland -c "CREATE DATABASE superset OWNER superset;"
```

**mkcert CA** (for Keycloak OIDC back-channel TLS) — copy to data-mesh ns:
```
kubectl -n weyland get secret weyland-mkcert-ca -o yaml | sed 's/namespace: weyland/namespace: data-mesh/' | kubectl apply -f -
```

**Argo sync:**
```
argocd app sync superset --core
```

---

## Gotchas (every one cost a cycle)

1. **`psycopg2` not in image** — the upstream 6.1.0 image lacks it. Until 2026-10-24 `bootstrapScript` pip-installed `psycopg2-binary trino authlib clickhouse-connect` unpinned into the venv on every start; they are now BAKED INTO `weyland-superset` (§ The image below), and the bootstrap installs nothing.

2. **`SUPERSET_SECRET_KEY` KeyError** — the secret must exist AND contain `SUPERSET_SECRET_KEY` before the pod starts. Chart generates `superset-env` from `supersetNode.connections`; `SUPERSET_SECRET_KEY` goes in `extraSecretEnv` so the chart includes it.

3. **Postgres connection refused** — Superset is meshed (`sidecar.istio.io/inject: "true"`) but the `data-mesh` namespace needed `kubectl label namespace data-mesh istio-injection=enabled`. Without it, the sidecar never injects → Postgres STRICT mTLS drops the connection with "server closed the connection unexpectedly" (no SSL handshake).

4. **Keycloak OIDC `Failed to add user to db session`** — `REQUESTS_CA_BUNDLE` must point at the mkcert CA (mounted from `weyland-mkcert-ca` secret at `/etc/ssl/weyland-ca/rootCA.pem`). Without it, the back-channel token exchange fails SSL verification → silent redirect loop.

5. **`WTF_CSRF_SSL_STRICT = False` + `ENABLE_PROXY_FIX = True`** — required behind Traefik TLS termination. Without proxy fix, Superset generates `http://` redirect URLs → mixed content / CSRF failures.

6. **Argo stuck sync** — if Argo shows "waiting for healthy state of Deployment/superset" and won't clear: `argocd app terminate-op superset --core` then `argocd app sync superset --core`. The Recreate strategy means the old pod must die before the new one starts — `terminate-op` clears the wedged operation so the sync can proceed.

7. **Bootstrap installs into wrong Python** (history: the bootstrap no longer installs; the image build uses the same system `pip` + `--target`) — early attempts used `/app/.venv/bin/pip` (venv has no pip) or `python3 -m pip` (venv python3 has no pip module). Only the system `pip` binary works; `--target` redirects the install into the venv's site-packages directory.

8. **DataHub secrets wiped on GMS restart** — `OIDC_CLIENT_SECRET` is stored in the `superset-env` k8s Secret (safe). But DataHub Secrets (for ingestion recipes) are lost on GMS pod restart — re-enter them in DataHub UI → Settings → Secrets after any GMS restart.

---

## The image — `weyland-superset` (B227 follow-on, 2026-10-24)

`k8s/superset/image/` builds `FROM apachesuperset.docker.scarf.sh/apache/superset:6.1.0@sha256:fb346452…` (the digest
the pod ran) plus `requirements.txt`: the nine packages the old bootstrap had added (psycopg2-binary 2.9.13, trino
0.340.0, clickhouse-connect 1.9.0, Authlib 1.8.0 and their five dependencies), installed `--no-deps` with the system
`pip` and `--target` into the venv. Measured 2026-10-24 on the running pod: the old unpinned install had ALSO written
newer metadata for 11 of the image's packages (cryptography 50.0.2, requests 2.34.2, urllib3 2.8.0, …) while Python kept
importing the image's own code (cryptography 46.0.5, …), so a scanner reported versions that never ran. The image
reproduces what ran: the base unchanged (no duplicate `dist-info`), every requirement of the nine met by the base, the
`postgresql` / `trino` / `clickhousedb` dialects load. Hand-tagged like `weyland-jupyter` (the chart takes `image.repository`
and `image.tag` separately, which the CI bump PR cannot rewrite); `images.tsv` notes it.

Build and push a new tag on rogueone (list the tags first and take the next FREE `vN`:
`curl -s https://registry.weyland.lab/v2/weyland-superset/tags/list`):

[rogueone]
```
docker build -t registry.weyland.lab/weyland-superset:<tag> /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/superset/image && bash /home/edwardmangini/IdeaProjects/weyland/scripts/push-image.sh registry.weyland.lab/weyland-superset:<tag>
```
Then set `image.tag` in `superset-values.yaml` and push. **Order matters:** the tag must be in the registry BEFORE
the values change reaches Argo (Recreate: a missing tag leaves Superset down in ImagePullBackOff). Roll back by
reverting the values commit; the drivers are the same versions, so nothing about the metadata DB changes.

## Database connections (Superset → sources)

Added via API on initial setup. If lost, re-run the setup script or add manually via **Settings → Database Connections**.

Key connections:
- `Trino` — `trino://superset@trino.data-mesh.svc.cluster.local:8443/iceberg`, password `TRINO_PW_SUPERSET`, engine
  params `{"connect_args": {"http_scheme": "https", "verify": "/etc/ssl/weyland-ca/rootCA.pem"}}` (B233; it was
  `trino://trino@…:8080` with no password before)
- `weyland`, `dagster`, `datahub`, `glitchtip`, `keycloak`, `lakefs`, `mlflow`, `nessie`, `sonarqube`, `superset`, `unleash` — all `postgresql+psycopg2://weyland:weyland_dev_password@weyland-postgres.weyland.svc.cluster.local:5432/<db>`

---

## Seed the marts dashboards

`scripts/superset_seed.py` (idempotent) creates/updates the Music/Health/Finance **marts datasets + charts +
the three `Weyland Marts — *` dashboards** over the Trino connection — no UI clicking. Re-run it after adding a
mart; it **updates an existing dashboard's layout** so newly-added charts land on it (before 2026-09-05 it
early-returned on an existing dashboard and silently skipped laying out new charts). `SUPERSET_PASSWORD` = the
Helm-bootstrapped DB-admin (`provider=db`, NOT Keycloak), from `scripts/.env` (gitignored):

```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts
set -a; . ./.env; set +a
python3 superset_seed.py
```

Run from a box that reaches `superset.weyland.lab` with the mkcert CA (rogueone/mother). Companions:
`superset_seed_extra.py` (raw ClickHouse marts), `superset_seed_cube.py` (Cube-backed). Prints each dataset/
chart/dashboard id; ends `Done: N mart datasets, M charts, 3 dashboards`.

---

## Monitoring

- `SupersetDown` + `SupersetWorkerDown` PrometheusRules in `k8s/data-mesh/superset-alerts.yaml`
- Uptime Kuma: add monitor for `https://superset.weyland.lab`
