# B1 — Data Mesh: design decisions (in progress)

Single-operator homelab mesh (weyland), built layer by layer. Decisions locked as we go.

> **Directional.** This is a scoping pass — some picks will swap at implementation time as reality bites.

## Cross-cutting principle — run-mode tiering
One node, so nothing heavy idles. Every component is tagged **always-on** (lightweight foundation,
discoverability) or **on-demand** (heavy/bursty — spun up per job/demo, scaled to zero otherwise).
- **KEDA** — the on-demand enabler: scale-to-zero + wake on triggers (Kafka lag, cron, HTTP).
- **Flink Kubernetes Operator** — per-job (Application mode) Flink clusters: spin up, run, tear down.

## Locked

### L1 — Storage / Data Product Layer
- **MinIO** — object-store foundation (existing).
- **Apache Iceberg** — table format for tabular data products.
- **Nessie** — Iceberg catalog + git-branching **versioning for TABLE products**.
- **lakeFS** — **versioning for NON-tabular/file products** (raw corpora, ML datasets, model artifacts).
- Rationale: Nessie versions Iceberg tables, lakeFS versions files — complementary, split by data type.

### L2 — Query / Federation
- **Trino** — single federated-SQL engine across Iceberg (via Nessie), Postgres/pgvector, and the rest.
- **DuckDB** — embedded/local analytical crunching (pairs with Arrow).
- **TimescaleDB** — hot time-series, as a **Postgres extension** (reuses existing Postgres; Trino-queryable). No InfluxDB. Cold/analytical time-series → Iceberg; ops metrics stay on Prometheus.

### L3 — Transform / Streaming / Orchestration
- **Orchestration → Dagster** (existing, **always-on** — the workhorse for real batch/micro-batch). **No Airflow.**
- **EL / ingestion → dlt** (general pulls, runs inside Dagster, **always-on** via Dagster) **+ Debezium** (CDC, **on-demand**). No Airbyte.
- **Transform → dbt Core + full ecosystem** + **SQLMesh** (kept). Adapters: dbt-trino, dbt-duckdb, dbt-postgres. Packages: dbt-utils, dbt-expectations (partial DQ), codegen, audit-helper. dbt docs overlaps L4 catalog (dedupe there).
- **Streaming → Kafka (Strimzi) + Flink, whole tier ON-DEMAND** (Debezium + Kafka + Flink spun up per CDC/stream job via KEDA + Flink Operator; for demo/play). Real work stays on Dagster batch.
- **KEDA** (always-on, tiny) + **Flink K8s Operator** — the on-demand machinery.

### L4 — Catalog / Contracts
- **DataHub** — the catalog (de-facto standard; **always-on** centerpiece). Accepts the weight (ES + its own internal Kafka + GMS + frontend + SQL). Its internal Kafka ≠ the on-demand Strimzi data Kafka. **ES exposed as a first-class shared service** (2026-06-24) — own service/endpoint, not DataHub-internal; the lab's single ES, reusable for search/log experiments.
- Drop **Amundsen** (discovery-only) and **OpenDataMeshPlatform** (redundant).
- **Contracts → DataHub native data products + contracts/assertions**, standardized on **ODCS** (Open Data Contract Standard).
- **dbt docs** folds into DataHub (it ingests dbt metadata). DataHub ingests **OpenLineage (Dagster) + Trino** → likely absorbs **Marquez** at L5.

### L5 — Governance / Security
- **Lineage → OpenLineage** (Dagster emits it) ingested into **DataHub**. **Drop Marquez** (DataHub is the lineage store/UI).
- **Identity/SSO → Keycloak** (always-on) — unified login across all UIs + the subjects authz policies bind to.
- **Data quality → dbt-expectations** (in-pipeline) **+ Soda** (standalone profiling/monitoring).
- **Authz → Ranger + OPA (both, in lanes):** Ranger = data-plane (Trino column/row masking, tag policies, audit); OPA = control-plane (services/k8s/Rego).

### L6 — Analytics
- **Cube** — serving semantic layer (REST/GraphQL/SQL + caching/rollups) in front of Trino.
- **dbt Semantic Layer (MetricFlow)** — dbt-native metric definitions (kept alongside Cube).
- **Apache Arrow** — plumbing only (DuckDB/Trino use it internally); no standalone deploy.

### L7 — BI / Dashboards
- **Lightdash** (primary, dbt-native — reads dbt models + metrics) **+ Superset** (the standard, ad-hoc/complex viz). Both **on-demand** (KEDA scale-to-zero). No Metabase.

### L8 — Data Science
- **JupyterHub** (KubeSpawner — per-session pods on-demand; hub always-on/tiny).
- **Feast** (feature store — data products → features → MLflow; serves the tuning/fine-tuning product; reuses Postgres).
- **Ray (KubeRay)** — on-demand distributed ML compute.

## Run-mode tiers
- **Always-on (foundation):** MinIO, Postgres (+TimescaleDB +pgvector), Nessie, lakeFS, Dagster, DataHub, Keycloak, Ranger, OPA, Cube, KEDA, Trino coordinator.
- **On-demand (KEDA / operators):** Trino workers, the streaming tier (Kafka/Strimzi + Debezium + Flink), Lightdash, Superset, JupyterHub sessions, Ray, Feast (training), Soda runs.

## Next
- Sequence into implementable slices + dependency order (storage → catalog/governance → query → transform → consumption).
- Map onto the **3 data products**: (1) model-eval, (2) store-inventory → recast as lineage/observability, (3) model-tuning feed → fine-tuning.
- Decisions are directional — expect swaps at implementation.
