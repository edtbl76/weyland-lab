# Trino — federation query engine (B65 Tier-2, 1st)

Single-node Trino in `data-mesh`. The keystone the lab queries the lake + relational stores through;
Superset / dbt / the B73 "use the data" work all ride on it. Manifest: `k8s/data-mesh/trino.yaml`
(deployed by the data-mesh Argo app). Always-on (~2 GB heap) — revisit KEDA at the footprint gate.

## Catalogs
- **`iceberg`** — the Nessie lake (`datasets.*` music gold, `catalog`, `eval`). **Uses Trino's NATIVE
  Nessie catalog** (`iceberg.catalog.type=nessie`, Nessie API v2), NOT the generic `type=rest` — the
  generic REST client forges a 403 at init against Nessie's `/iceberg` even though the infra is clean.
  See [[trino-nessie-native-catalog]].
- **`postgresql`** — the `weyland` DB (JDBC; works over the mesh to STRICT Postgres — it's TCP, so Istio
  passes it through).
- `system` — Trino internals.

## How to connect
- **CLI:** `kubectl -n data-mesh exec -it deploy/trino -- trino` → `trino>` prompt.
- **IntelliJ / DataGrip:** forward port 8080 via the IntelliJ Kubernetes plugin (Services → trino →
  Forward Ports), then a **Trino** data source at `jdbc:trino://localhost:8080`, user any / no password.
- **Web UI:** `https://trino.weyland.lab` (forward-auth → Keycloak, then Trino username-only login). It's
  a **monitoring console** (running queries, timings, cluster), NOT a query editor — use Superset/CLI/IDE
  to run SQL.

## Gotchas (all cost time, all in the manifest now)
- **Native Nessie catalog**, not generic REST (above).
- **AVX/Proxmox:** Lance + other native libs need AVX-512 → required `cpu: host` on the mother VM
  ([[proxmox-vm-cpu-host-avx]]); unrelated to Trino but surfaced in the same push.
- **`http-server.process-forwarded=true`** — without it the web UI 406s behind Traefik+Istio
  ("Server configuration does not allow processing of the X-Forwarded-For header").
- **`/metrics` auth:** OpenMetrics endpoint wants **Basic auth with username + EMPTY password** (no-auth
  mode); the ServiceMonitor uses `basicAuth` → `trino-metrics-auth` secret (password = ``). Manual curl
  also needs `-H "Accept: text/plain"` (it 406s on `*/*`); Prometheus sends the right Accept itself.
- **No catalog auto-reload:** Trino reads catalogs/config at startup only → after a configmap change,
  `kubectl -n data-mesh rollout restart deploy/trino` (and the configmap must be synced/applied first).

## Observability
- **Prometheus** ServiceMonitor scrapes `/metrics` (basicAuth) → `trino_*` series in Grafana Explore.
- **Istio** sidecar already exports request rate/latency/errors (`istio_requests_total{destination_workload="trino"}`).
- **Kuma** HTTP monitor on `https://trino.weyland.lab` (reports UP off the gated page, like the other SSO'd UIs).

## DataHub
DataHub `trino` ingestion source (`k8s/data-mesh/datahub-ingestion/trino.recipe.yaml`) catalogs the
`iceberg` catalog's tables as `trino`-platform datasets with **sibling + upstream lineage to the iceberg
platform** (`catalog_to_connector_details`) — Trino shows as the query layer over the lake.

## Secrets (imperative → SealedSecrets at B69)
- `trino-secret` — MINIO_ACCESS_KEY / MINIO_SECRET_KEY / WEYLAND_PG_PASSWORD (catalog creds).
- `trino-metrics-auth` — username=prometheus, password=`` (empty) for the /metrics scrape.
