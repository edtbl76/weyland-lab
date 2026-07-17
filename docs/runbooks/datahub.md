# DataHub — the metadata catalog (B1.3)

**What:** DataHub is the mesh's metadata catalog + lineage + governance surface — every store, table, dbt mart,
BI chart, and Dagster asset shows up here with its schema, lineage, domains/data-products, glossary terms, and
data-quality assertions. Two mechanisms feed it: **native managed-ingestion** (recipe-driven source scans that
crawl each store) and a **custom git-emit** (a Dagster job that walks our asset graph and pushes catalog +
lineage over the REST emitter).

**Where:**
- UI: **https://datahub.weyland.lab** (native Keycloak OIDC — no forward-auth; DataHub does its own auth-code flow).
- In-cluster: GMS (the backend) at `datahub-datahub-gms.data-mesh.svc.cluster.local:8080`; frontend (React UI) is
  `ClusterIP` behind the ingress.
- Manifests: `k8s/data-mesh/datahub-values.yaml` (chart `1.0.1` / DataHub v1.6.0) + `datahub-prerequisites-values.yaml`,
  Argo helm app. Ingestion recipes: `k8s/data-mesh/datahub-ingestion/*.recipe.yaml` (+ its `README.md` = the
  source-of-record index). Custom emitter: `services/weyland-dagster/weyland_pipeline/datahub_emit.py`.
- Metadata store = the shared **weyland-postgres** (`datahub` DB); search/graph = the bundled OpenSearch 2.19.5.
- Governance-as-code (domains/products/glossaries/structured-properties/docs-links) is all emitted from git —
  see [[datahub-governance-layer]].

## Architecture

Helm chart, ns `data-mesh`. Every pod is meshed (`sidecar.istio.io/inject`) so GMS + the systemUpdate Job reach
STRICT-mTLS Postgres; the istio sidecar CPU request is shrunk (`proxyCPU: 25m`) for the CPU-tight node, and GMS +
frontend are **ClusterIP** (a default `LoadBalancer` stays `<pending>` on k3s → Argo's sync hangs forever on
"waiting for healthy state of Service"). The **acryl-datahub-actions** pod runs the actions framework **and** the
managed-ingestion executor as a subprocess. Frontend does native Keycloak OIDC; its JVM back-channel to
`keycloak.weyland.lab` needs a truststore of system `cacerts` + the mkcert root, built by an initContainer
(see [keycloak.md](keycloak.md)).

## Two ways things get cataloged

**1. Native managed-ingestion (recipes).** UI-configured sources (Ingestion → Sources) that crawl a store on a
schedule. Because DataHub stores those source configs in GMS/Postgres (**not** git), they don't survive a rebuild —
so the committed `datahub-ingestion/*.recipe.yaml` files are the **source-of-record**: 14 recipes today (Iceberg,
Grafana, dbt, Postgres, Trino, Mongo, Neo4j, Kafka/Redpanda, MLflow, Superset, Cassandra, ClickHouse, CockroachDB,
MusicBrainz-Postgres). Every recipe points at the **in-cluster service**, never the forward-auth ingress (which
401s API calls); the executor is meshed so it reaches both PERMISSIVE and STRICT-mTLS targets. See the
`datahub-ingestion/README.md` table for schedules + which Secret each needs. Notable per-store gotchas:
Cockroach uses `cockroachdb://` not the pg dialect ([[cockroachdb-pg-wire-not-dialect]]); the ClickHouse source
needs its password via a `users.d` Secret ([[clickhouse-tier2-hydration]]); the mongo source needs creds inline
in `connect_uri` ([[datahub-ingestion-secrets-durable]]).

**2. Custom git-emit (`datahub_catalog_emit_job`).** A Dagster job (`definitions.py`) that **replaces** the
acryl datahub-dagster sensor — that sensor is built on Dagster's `run_status_sensor`, broken on 1.7.3+
(dagster#21526) and dead on our 1.13.10 (emits nothing). Instead it walks the asset graph directly and pushes
Datasets + UpstreamLineage + group tags to GMS via the REST emitter (idempotent, upsert, version-proof). It runs
`in_process_executor` (27 dependency-free emit ops otherwise each re-import the ~1.1 GB defs → OOM), on
`cron 40 */6 * * *` (every 6h). The same file also emits domains, data products, glossaries, structured
properties, docs-links, ownership, queries, and the dbt/OpenLineage + Soda assertions ([[datahub-governance-layer]],
[soda.md](soda.md), [dbt.md](dbt.md)).

## GMS + token

Metadata-service authentication is **on**. The emitters read `DATAHUB_GMS_URL`
(default `http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080`) and `DATAHUB_GMS_TOKEN` — a DataHub PAT.
In the Dagster user-code pod that token comes from the `datahub-token` Secret (key `token`, in the dagster ns),
wired in `k8s/dagster/user-code.yaml`. Mint the PAT in the DataHub UI (Settings → Access Tokens); if SSO hides
the token UI, mint a service token via the admin API ([[datahub-ingest-gated-services]]).

The chart's `provisionSecrets` is **pinned off** (`metadata_service_authentication.provisionSecrets.enabled: false`):
the chart otherwise regenerates `datahub-auth-secrets` on every render → GMS and frontend end up with mismatched
signing keys (frontend token → 401 at GMS, "Failed to provision user") **and** selfHeal sees the churning Secret as
perpetual drift → GMS never reports Healthy → syncs hang. We create `datahub-auth-secrets` ourselves (fixed
values, out of git).

## Re-running ingestion

- **A native source:** DataHub UI → Ingestion → Sources → the source → **Run**. If DataHub was rebuilt and the
  source is gone, recreate it by pasting the matching `*.recipe.yaml` (Ingestion → Sources → Create → paste) and
  re-creating its DataHub Secret(s).
- **The custom emit:** launch **`datahub_catalog_emit_job`** in the Dagster UI (or wait for the 6-hourly schedule).

## Gotchas

- **The durable-secrets trap.** UI-entered DataHub Secrets are **wiped** whenever GMS / the system DB is reset →
  recurring "no password supplied" ingestion failures. Durable fix: inject the creds as **`extraEnvs` from a k8s
  Secret** (`datahub-ingestion-secrets`, ns data-mesh) on the `acryl-datahub-actions` pod — the recipe `${VAR}`
  refs resolve from that pod's ENV (ingestion runs as a subprocess there), so they survive resets. `optional: true`
  on each key lets the pod start before every value is populated. Create the Secret **once**, out-of-band, with
  values pulled from the source secrets in `weyland`. Some sources still need their password **in the live source
  config too** (mongo `connect_uri`) — [[datahub-ingestion-secrets-durable]].
- **Actions pod OOM.** `acryl-datahub-actions` runs ingestion; profiling-enabled Postgres/MusicBrainz runs
  exit-137'd at 512 Mi → hung ingestions. Ceiling raised to 1 Gi (request stays 256 Mi so it reserves little idle).
  If a big profiling run still exit-137s, bump further or sleep idle stores ([[store-scaler-easy-button]]) to free RAM.
- **GlitchTip drops oversized events** from big-dep apps — unrelated to DataHub but bites the Dagster job's error
  reporting ([[glitchtip-oversized-event-drop]]).
- **Global "browse all Data Contracts"** GraphQL nulls every hit — a DataHub resolver bug, not our data; the
  per-dataset Validations tab works. Don't chase it ([[datahub-datacontract-browse-broken]]).

## Links
- [[datahub-governance-layer]] · [[datahub-ingestion-secrets-durable]] · [[datahub-ingest-gated-services]] ·
  [[dagster-datahub-1.13-blocked]] · [nessie.md](nessie.md) · [dbt.md](dbt.md) · [soda.md](soda.md) ·
  [keycloak.md](keycloak.md) · `k8s/data-mesh/datahub-ingestion/README.md`
