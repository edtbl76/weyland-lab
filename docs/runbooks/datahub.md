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
- **Keep NO UI Secrets — they shadow the env (found 2026-09-27).** A UI Secret with the same name wins over the pod
  env, and UI Secrets are encrypted with DataHub's encryption key, which the chart regenerates (it is not sealed).
  After a regeneration every UI Secret failed to decrypt ("AES-GCM Tag mismatch") and resolved EMPTY: the dbt source
  failed daily for 10+ days on `NoCredentialsError` while its env value was never used; sources whose services
  tolerate an empty credential kept reporting SUCCESS. Fix applied: all 7 undecryptable UI Secrets deleted, and the
  missing `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` added to `datahub-ingestion-secrets` (copied from `nessie-secret`
  s3-access-key / s3-secret-key, resealed). Rule: every `${VAR}` a recipe uses is a key in `datahub-ingestion-secrets`
  and an `extraEnvs` entry; the UI Secrets list stays empty. Check: `listSecrets` returns `[]`.
  With creds fixed, dbt then failed on a second, masked bug: DataHub 1.6.0 (and 1.7.0.13) emits dbt semantic models
  with columns typed `entity:primary` and crashes resolving that as a Trino type (`KeyError: 'entity:primary'`).
  `entities_enabled.semantic_models: No` in `dbt.recipe.yaml` (pushed to the live source) → **dbt SUCCESS
  2026-09-27**, first success in at least 10 days.
- **A failing ingestion used to alert nobody** (fixed by the ingestion watchdog below, B197). The dbt and MLflow
  sources both failed every day for 10+ days unnoticed.
  MLflow's cause: MLflow 3's built-in "MLflow Demo" experiment logs dataset inputs with no schema, and the DataHub
  1.6.0 (and 1.7.0.13) mlflow source crashes on `json.loads(None)`; the demo experiment was soft-deleted
  (`POST /api/2.0/mlflow/experiments/restore` brings it back).
- **Actions pod OOM.** `acryl-datahub-actions` runs ingestion; profiling-enabled Postgres/MusicBrainz runs
  exit-137'd at 512 Mi → hung ingestions. Ceiling raised to 1 Gi (request stays 256 Mi so it reserves little idle).
  If a big profiling run still exit-137s, bump further or sleep idle stores ([[store-scaler-easy-button]]) to free RAM.
- **GlitchTip drops oversized events** from big-dep apps — unrelated to DataHub but bites the Dagster job's error
  reporting ([[glitchtip-oversized-event-drop]]).
- **Global "browse all Data Contracts"** GraphQL nulls every hit — a DataHub resolver bug, not our data; the
  per-dataset Validations tab works. Don't chase it ([[datahub-datacontract-browse-broken]]).

## Ingestion watchdog (B197, 2026-09-28)

`datahub-ingestion-watchdog` (CronJob, ns `weyland`, daily **05:55 NY**; script `scripts/datahub_ingestion_check.py`)
reads every managed-ingestion source and its last 20 runs from GMS GraphQL and posts to Alertmanager → Telegram:

| Alert | When |
|---|---|
| `DataHubIngestionFailed` | the latest run is FAILURE or ABORTED |
| `DataHubIngestionStale` | no SUCCESS within 2x the source's schedule (1h floor) — a run orphaned in RUNNING or a CANCELLED run is not a success; also a source with no schedule that is not an accepted on-demand one |
| `DataHubIngestionNeverRan` | a scheduled source with no run at all |

Each alert carries `ingestion_source="<name>"`. One message per broken source per day (the next morning re-sends it
while the condition holds). GMS unreachable, GraphQL errors, or an empty/partial source list is exit 2, and an alert
that cannot be POSTed is exit 1 — both fail the Job, so `ScheduledJobFailed` pages; never a silent pass. Accepted
on-demand sources are listed by URN in the script (`ACCEPTED_ON_DEMAND`: `[CLI] dbt`).

**Run it now** instead of waiting for 05:55:

[mother]
```
kubectl -n weyland create job datahub-ingestion-watchdog-now --from=cronjob/datahub-ingestion-watchdog && kubectl -n weyland wait --for=condition=complete job/datahub-ingestion-watchdog-now --timeout=180s; kubectl -n weyland logs job/datahub-ingestion-watchdog-now; kubectl -n weyland delete job datahub-ingestion-watchdog-now
```
Expect `checked 17 source(s): 0 alert(s) fired` on a healthy catalog.

**Alert drill** — one real alert for one source (a budget shrunk to ~17s makes it stale), then clean up:

[mother]
```
kubectl -n weyland create job datahub-ingestion-watchdog-drill --from=cronjob/datahub-ingestion-watchdog --dry-run=client -o json | python3 -c "import json,sys;j=json.load(sys.stdin);c=j['spec']['template']['spec']['containers'][0];c['env']+=[{'name':'ONLY_SOURCE','value':'Trino - Weyland'},{'name':'BUDGET_FACTOR','value':'0.0001'}];print(json.dumps(j))" | kubectl create -f - && kubectl -n weyland wait --for=condition=complete job/datahub-ingestion-watchdog-drill --timeout=180s; kubectl -n weyland logs job/datahub-ingestion-watchdog-drill; kubectl -n weyland delete job datahub-ingestion-watchdog-drill
```
Expect `ALERT DataHubIngestionStale source='Trino - Weyland'`, the alert active in Alertmanager, and a Telegram message.

**After editing the script:** `bash scripts/embed-datahub-ingestion-watchdog.sh` (the bats identity test fails until
you do).

## Links
- [[datahub-governance-layer]] · [[datahub-ingestion-secrets-durable]] · [[datahub-ingest-gated-services]] ·
  [[dagster-datahub-1.13-blocked]] · [nessie.md](nessie.md) · [dbt.md](dbt.md) · [soda.md](soda.md) ·
  [keycloak.md](keycloak.md) · `k8s/data-mesh/datahub-ingestion/README.md`
