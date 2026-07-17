# Nessie — Iceberg REST catalog + table versioning (B1.2)

**What:** Nessie is the **catalog** for the data mesh's Iceberg tables — it maps table names to their current
metadata **and** gives them git-style versioning (branches, commits, tags) over the lake. It's the single catalog
that Trino, dbt, and Flink all read/write, so a table Flink sinks or dbt builds is instantly visible to Trino and
auto-cataloged by DataHub. It's the storage foundation of the mesh's table tier ([[data-mesh-b1.2-storage]]).

**Where:**
- UI + API: **https://nessie.weyland.lab** (Keycloak forward-auth — gates the UI, the Iceberg REST endpoint, and
  the API v2 alike).
- In-cluster: `nessie.data-mesh.svc.cluster.local:19120` — everything is served on 19120:
  - **Iceberg REST catalog** at `/iceberg`
  - **Nessie API v2** at `/api/v2` (what the native catalog clients use)
  - the **UI** at `/`
- Manifest: `k8s/data-mesh/nessie.yaml` (`ghcr.io/projectnessie/nessie:0.107.9`). Secret: `nessie-secret`
  (`nessie-secret.example.yaml` is the committed template).
- **Version store** = the shared **weyland-postgres** (`nessie` DB, JDBC2). **Warehouse** = MinIO `s3://warehouse/`.

## Architecture

Raw `Deployment`, ns `data-mesh`, `strategy: Recreate`, meshed (`sidecar.istio.io/inject`) — the Postgres version
store is STRICT mTLS, so without the sidecar the JDBC connection resets (read ECONNRESET) ([[postgres-strict-needs-mesh]]).
Nessie is a Quarkus app: the app + REST + Iceberg catalog on `:19120`, health/management on `:9000` (pod-local
`/q/health/*` — **not** MinIO's 9000). Two persistence pieces:

- **Version store (Postgres JDBC2).** Holds the branch/commit graph. `NESSIE_VERSION_STORE_TYPE=JDBC2` +
  `NESSIE_VERSION_STORE_PERSIST_JDBC_DATASOURCE=postgresql` (the **named** datasource — mixing in the legacy
  unnamed `QUARKUS_DATASOURCE_JDBC_URL` silently fails to find the DB). Schema auto-migrates.
- **Warehouse (MinIO).** The actual Iceberg data + metadata files live in `s3://warehouse/`. Nessie owns the S3
  creds and vends them to clients. `PATH_STYLE_ACCESS=true`, `AUTH_TYPE=STATIC`, `REGION=us-east-1` — all
  mandatory for MinIO + static creds.

## How Trino / dbt / Flink use it

All three point at **the same** `main` ref and the same MinIO warehouse, so writes from one are readable by the others:

- **Trino** — its `iceberg` catalog uses Trino's **native Nessie** connector (`k8s/data-mesh/trino.yaml`):
  ```
  iceberg.catalog.type=nessie
  iceberg.nessie-catalog.uri=http://nessie.data-mesh.svc.cluster.local:19120/api/v2
  iceberg.nessie-catalog.ref=main
  iceberg.nessie-catalog.default-warehouse-dir=s3://warehouse
  ```
  ⚠ It's the **native** nessie type, NOT `iceberg.catalog.type=rest` — the generic REST client 403'd against
  Nessie's `/iceberg` endpoint even with the infra proven clean ([[trino-nessie-native-catalog]]).
- **dbt** — dbt-trino writes **through Trino** into that same `iceberg` catalog (`dbt/profiles.yml`,
  `database: iceberg`), so dbt marts land in Nessie/MinIO. See [dbt.md](dbt.md).
- **Flink** — creates the catalog directly against the Iceberg-REST/Nessie API
  (`CREATE CATALOG nessie WITH ('catalog-impl'='org.apache.iceberg.nessie.NessieCatalog',
  'uri'='http://nessie.data-mesh.svc.cluster.local:19120/api/v2', ref `main`, S3FileIO → MinIO) — see
  `k8s/flink/sql/*.sql` and [[flink-streaming-tier-b83]].

Because every engine shares `main` + `s3://warehouse/`, a Flink sink or a dbt `run` is immediately queryable in
Trino/Superset and auto-cataloged by DataHub's iceberg source ([datahub.md](datahub.md)).

## Branch / commit basics

Nessie is git-for-data: the default branch is **`main`**, and every catalog engine here reads/writes `main`.
Because the API is gated by forward-auth, use the **in-cluster service** for CLI / curl (the ingress 401s API
calls) ([[data-mesh-b1.2-storage]]). From a pod in-cluster:
```
# list refs (branches/tags) on API v2
curl -s http://nessie.data-mesh.svc.cluster.local:19120/api/v2/trees

# the Iceberg REST config endpoint (what an Iceberg client bootstraps from)
curl -s http://nessie.data-mesh.svc.cluster.local:19120/iceberg/v1/config
```
You can branch (`main` → an experiment ref), commit table changes on it, and merge back — but nothing here points
an engine at a non-`main` ref today, so treat branching as an isolation tool for experiments, not routine ops.

## Common ops (on **mother**)

Restart (Recreate rolls the single pod cleanly):
```
kubectl -n data-mesh rollout restart deploy/nessie
kubectl -n data-mesh logs -f deploy/nessie -c nessie
```

## Gotchas

- **Meshed, or Postgres resets the JDBC connection** ([[postgres-strict-needs-mesh]]).
- **JDBC2 needs the *named* datasource** (`postgresql`) — the legacy unnamed URL silently won't find the DB.
- **The S3 secret name must be HYPHEN-FREE.** SmallRye maps env vars to config keys, and env vars can't express a
  hyphen (`S3_CREDS_NAME` → `s3.creds.name`, not `s3-creds.name`). So the creds secret-ref is `s3creds`
  (`S3CREDS_NAME`/`S3CREDS_SECRET` → the URN `urn:nessie-secret:quarkus:s3creds`). The `access-key` value is a flat
  secret-reference URN, not the literal key (upstream nessie#11759). See the comments in `nessie.yaml`.
- **Native Nessie can't see nested namespaces** from Trino (dbt keeps marts in a single flat schema for this
  reason — see the note in `dbt/profiles.yml`).
- **Forward-auth blocks CLI/API** — automation uses the in-cluster svc, not `nessie.weyland.lab`.

## Links
- [[data-mesh-b1.2-storage]] · [[trino-nessie-native-catalog]] · [[postgres-strict-needs-mesh]] ·
  [[flink-streaming-tier-b83]] · [trino.md](trino.md) · [dbt.md](dbt.md) · [datahub.md](datahub.md) ·
  [storage-minio.md](storage-minio.md)
