# weyland IDP — runbook (B3)

Internal Developer Platform — **Backstage** under the hood, but named tool-neutrally (`weyland-idp`,
`idp.weyland.lab`, image `weyland-idp:local`) so it can be swapped for Port/Roadie/etc. without renaming.
Slices A (Software Catalog) + B (TechDocs + Catalog Graph) are live. Slice C (Scaffolder) is built but **parked → B42** — the template lists, but execution hits a node-fetch/gzip `Premature close` bug on the GitHub API.

- App (scaffolded monorepo): `services/weylandidp/` — new frontend + backend system, Backstage CLI ~0.36, Node 22/24, Yarn 4.
- Catalog (tool-agnostic, lives outside the app): `catalog/weyland-catalog.yaml` (~24 entities: Domain → 3 Systems → Components/Resources/APIs). Read straight from the **public repo** via `catalog.locations: type: url` (B41) — no ConfigMap copy; Backstage polls git and re-ingests on change.
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
The **production app-config** is mounted from a ConfigMap, so a config change is a ConfigMap-update +
`rollout restart` — **no image rebuild**. (The catalog is no longer a ConfigMap — it's read from the repo via
`type: url`, see below.)
- `weyland-idp-config` ← `services/weylandidp/app-config.production.yaml`, **subPath-mounted over**
  `/app/app-config.production.yaml` (overrides the image-baked copy).
```
kubectl create configmap weyland-idp-config -n weyland --from-file=app-config.production.yaml=$HOME/lab/weyland-platform/app-config.production.yaml
```
> Tilde trap: `--from-file=key=~/path` does NOT expand `~` (mid-argument) — use `$HOME` or `cd` into the dir.
> The `catalog.locations` target points at the public repo:
> `https://github.com/edtbl76/weyland-lab/blob/main/nodes/mother/lab/weyland-platform/catalog/weyland-catalog.yaml`.

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
- **Auto-published by Dagster (B41).** The `weyland_techdocs_job` (asset `techdocs_publish`, group `techdocs`,
  **hourly** `weyland_techdocs_schedule`) clones the repo, runs `mkdocs build`, and uploads the site to the
  `techdocs` bucket under `default/component/weyland-docs/`. Pure Python (`mkdocs-techdocs-core` + the `minio`
  client) — **no `@techdocs/cli`, no node** in the Dagster image; reuses the pod's existing `GIT_*` + `MINIO_*`
  env. To force a refresh now, materialize the job in Dagit (`dagster.weyland.lab` → `weyland_techdocs_job`).
- **Catalog Graph:** `@backstage/plugin-catalog-graph/alpha` added to `packages/app/src/App.tsx` `features`.
  The standalone nav page is empty without a root entity — the useful view is the per-entity Catalog Graph card.
- **Mermaid** diagrams render as code (no official addon) → parked, **B40**.

## Keeping the IDP in sync (B41)
Both surfaces self-heal from the repo — no manual republish:
- **Catalog** → `catalog.locations: type: url` off public GitHub; Backstage's UrlReader polls (~150s) and
  re-ingests on change. `integrations.github: [{host: github.com}]` enables the unauthenticated public read
  (no token). The catalog ConfigMap is **gone** — the repo is the only source of truth.
- **TechDocs** → the hourly Dagster `weyland_techdocs_job` above. (Catalog is *fetched* live because it needs no
  build; TechDocs is *built+published* because servable HTML can't live in the repo. Different tools, same goal.)

## Scaffolder — golden-path templates (slice C — PARKED → B42)
> **Built, not working.** The template lists at `/create`, but running it fails: `fetch:template` + publish
> call the GitHub **API**, and this image's **node-fetch v2 chokes on gzip** (`Gunzip … Premature close`).
> The catalog read works because it uses `raw.githubusercontent.com` (uncompressed). Fix options in **B42**.
> The token was reverted (it took the catalog down once); re-add it only as part of the B42 fix.

"Create" in the IDP runs a **Scaffolder** template that renders a skeleton and opens a **GitHub PR**.
- **Template:** `catalog/templates/k8s-service/template.yaml` (kind `Template`) + `skeleton/` (Nunjucks
  `${{ values.x }}`). Registered via a `Location` in `weyland-catalog.yaml`, so it auto-syncs with the catalog
  (B41) — **no separate config**. The "new k8s service" template renders a meshed Deployment + Service +
  Ingress (Traefik TLS) + `catalog-info.yaml` + a runbook stub, at their real repo paths.
- **Frontend:** `@backstage/plugin-scaffolder/alpha` added to `packages/app/src/App.tsx` `features` (needs an
  **app image rebuild** — the dep was already in `package.json`, just unwired).
- **Backend:** `plugin-scaffolder-backend` + `-module-github` were already in `index.ts` (no rebuild for those).
- **PR auth:** `integrations.github[].token: ${GITHUB_TOKEN}` — a **fine-grained PAT** scoped to
  `edtbl76/weyland-lab` (Contents + Pull requests: **write**), added to `weyland-idp-secret` as key
  `GITHUB_TOKEN` (secretKeyRef is `optional: true`, so the IDP boots without it — only the PR step fails).
  Create the PAT + add the key out-of-band; never commit it.
- **Flow:** Create → pick "New k8s service" → fill name/image/port/namespace → Scaffolder renders + pushes
  branch `scaffold/<name>` + opens a PR. Review/merge; the new service then catalog-syncs in via B41.

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
