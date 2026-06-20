# weyland IDP — runbook (B3)

Internal Developer Platform — **Backstage** under the hood, but named tool-neutrally (`weyland-idp`,
`idp.weyland.lab`, image `weyland-idp:local`) so it can be swapped for Port/Roadie/etc. without renaming.
Slices A (Software Catalog) + B (TechDocs + Catalog Graph) are live; slice C (Scaffolder template) is pending.

- App (scaffolded monorepo): `services/weylandidp/` — new frontend + backend system, Backstage CLI ~0.36, Node 22/24, Yarn 4.
- Catalog (tool-agnostic, lives outside the app): `catalog/weyland-catalog.yaml` (~24 entities: Domain → 3 Systems → Components/Resources/APIs).
- k8s: `k8s/weyland-idp/weyland-idp.yaml` (Deployment + Service + Ingress). DB: a `weyland_idp` role in the shared Postgres.

## Build — from git, reproducible
The app uses a **multi-stage `Dockerfile`** (`services/weylandidp/Dockerfile`) that installs + compiles + bundles
entirely inside Docker from the committed source. Host needs **only Docker + BuildKit** — no Node/Yarn, no
pre-build. `yarn.lock` + `.yarn/releases` pin everything. (The create-app default `packages/backend/Dockerfile`
is the host-build variant — superseded; do not use it.)
```
DOCKER_BUILDKIT=1 docker image build . -t weyland-idp:local
```
Ship to k3s (no registry): `docker save weyland-idp:local -o /tmp/weyland-idp.tar`, scp to mother, then
`sudo k3s ctr images import ~/weyland-idp.tar`. (Piping `docker save | ssh 'sudo …'` fails — sudo has no TTY.)

## Config — ConfigMap, not baked
Both the **catalog** and the **production app-config** are mounted from ConfigMaps, so changes are a
ConfigMap-update + `rollout restart` — **no image rebuild**:
- `weyland-idp-catalog` ← `catalog/weyland-catalog.yaml`, mounted at `/catalog`.
- `weyland-idp-config` ← `services/weylandidp/app-config.production.yaml`, **subPath-mounted over**
  `/app/app-config.production.yaml` (overrides the image-baked copy).
```
kubectl create configmap weyland-idp-catalog -n weyland --from-file=weyland-catalog.yaml   # run from the catalog/ dir
kubectl create configmap weyland-idp-config  -n weyland --from-file=app-config.production.yaml=$HOME/lab/weyland-platform/app-config.production.yaml
```
> Tilde trap: `--from-file=key=~/path` does NOT expand `~` (mid-argument) — use `$HOME` or `cd` into the dir.

## Postgres
Reuses the shared Postgres; Backstage creates its own `backstage_plugin_*` DBs, so the role needs `CREATEDB`:
```
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE ROLE weyland_idp LOGIN PASSWORD 'weyland_dev_password' CREATEDB;"
kubectl create secret generic weyland-idp-secret -n weyland --from-literal=POSTGRES_USER=weyland_idp --from-literal=POSTGRES_PASSWORD=weyland_dev_password --from-literal=BACKEND_SECRET=$(openssl rand -hex 32)
```

## Deploy
```
kubectl apply -f k8s/weyland-idp/weyland-idp.yaml && kubectl rollout status deploy/weyland-idp -n weyland
```
At `https://idp.weyland.lab` → **Enter** (guest). (DNS: `*.weyland.lab` is a CoreDNS wildcard → mother, but a
machine resolving via `/etc/hosts` needs a `192.168.1.243 idp.weyland.lab` line.)

## TechDocs (slice B) + Catalog Graph
`docs/` renders in-app as TechDocs, built **externally** and served from MinIO (no mkdocs/Docker in the pod):
- `mkdocs.yml` (repo root, `docs_dir: docs`, `techdocs-core`) + catalog entity `weyland-docs`
  (`backstage.io/techdocs-ref: dir:.`).
- `app-config.production.yaml`: `techdocs.builder: external` + `publisher.type: awsS3` → MinIO
  (`minio.minio.svc:9000`, bucket `techdocs`, creds from `aidlc-kb-minio-secret`).
- Build + publish (rogueone): `python3 -m venv /tmp/tdvenv && /tmp/tdvenv/bin/pip install mkdocs-techdocs-core`,
  then `PATH="/tmp/tdvenv/bin:$PATH" npx @techdocs/cli generate --source-dir . --output-dir ./site-techdocs --no-docker`,
  `mc mb weyland/techdocs`, then
  `NODE_EXTRA_CA_CERTS="$(mkcert -CAROOT)/rootCA.pem" AWS_ACCESS_KEY_ID=admin AWS_SECRET_ACCESS_KEY=weyland_dev_password AWS_REGION=us-east-1 npx @techdocs/cli publish --publisher-type awsS3 --storage-name techdocs --entity default/Component/weyland-docs --directory ./site-techdocs --awsEndpoint https://s3.weyland.lab --awsS3ForcePathStyle`.
  (Publish needs the mkcert CA via `NODE_EXTRA_CA_CERTS`; the Backstage backend reads MinIO over in-cluster HTTP.)
- **Catalog Graph:** `@backstage/plugin-catalog-graph/alpha` added to `packages/app/src/App.tsx` `features`.
  The standalone nav page is empty without a root entity — the useful view is the per-entity Catalog Graph card.
- **Mermaid** diagrams render as code (no official addon) → parked, **B40**.

## Gotchas hit (don't repeat)
- **STRICT-Postgres needs the mesh.** The pod MUST carry `sidecar.istio.io/inject: "true"` or every plugin dies
  with `read ECONNRESET` (Postgres's Envoy resets the plaintext connection). See [[postgres-strict-needs-mesh]]
  / [service-mesh-istio.md](service-mesh-istio.md).
- **Guest auth in production.** `auth.providers.guest` returns **403** on `/api/auth/guest/refresh` under
  `NODE_ENV=production` (→ catalog API 401s → "Could not fetch catalog entities"). Fix:
  `auth.providers.guest.dangerouslyAllowOutsideDevelopment: true` (LAN-only + allow-all policy make it OK).
- **⚠️ THE big one — compression breaks internal node-fetch (every TechDocs page 500'd).** The new-backend
  default `compression()` middleware gzips+chunks responses (no Content-Length); the internal **node-fetch v2**
  client (techdocs/search → catalog) throws `ERR_STREAM_PREMATURE_CLOSE` reading chunked bodies (browsers handle
  them fine). **Fix:** override `rootHttpRouterServiceFactory` in `packages/backend/src/index.ts` to drop
  `middleware.compression()` (the default chain minus that one line). **A rebuild WITHOUT this change silently
  reintroduces the bug.** It is NOT Istio/Node/DNS — the iptables prove port 7007 + `127.0.0.1` are RETURN'd
  (loopback bypasses Envoy); the tell was the catalog logging `200 0` (chunked, no length) vs `200 231` (buffered).
