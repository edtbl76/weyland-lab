# Flink streaming-processing tier — design (B83, B1.5 completion)

**Status:** design agreed 2026-07-13. Build starting. Tracker: Linear EMA-72. Full roadmap entry: `docs/backlog.md` → B83.

## Intent

Complete the B1.5 streaming tier. Redpanda + Debezium already produce topics (`datasets.*` Avro events,
`cdc.*` Debezium CDC), but **nothing processes them**. Flink is the missing stream-processing engine.
Multipurpose by design: real-time analytics AND CDC→lakehouse materialization, on one cluster.

## Decisions (from the brainstorm)

| Decision | Choice | Why |
|---|---|---|
| Purpose | Multipurpose — RTA + CDC materialization | user wants both on one Flink |
| Deployment | Flink K8s Operator → **one session cluster** | multipurpose ⇒ submit many jobs to one long-running cluster |
| Tiering | **always-on** (JM + 1 TM); KEDA-later | CDC materialization is a continuous consumer; scale-to-zero would stale it. Node has headroom (mother 64 GB post-B79) |
| Authoring | **Flink SQL** for the 2 real jobs + **1 Java + 1 PyFlink** example | SQL is right for both real jobs; session cluster is job-agnostic so both code surfaces are free optionality |
| Mesh | **sidecar OFF** | long-lived Kafka TCP behind Envoy = half-open stall risk (neo4j-bolt lesson); Nessie/MinIO are PERMISSIVE (un-meshed client OK); never touches STRICT core Postgres |
| Catalog | Flink Iceberg connector on the **same Nessie catalog** as Trino/dbt | outputs land in `iceberg.*` → queryable in Trino/Superset + auto-cataloged by DataHub iceberg source |
| State | RocksDB + checkpoints → MinIO `s3://flink/checkpoints` | exactly-once + recovery for the CDC upsert |

## Architecture

```
Redpanda topics ──► Flink session cluster (data-mesh, sidecar off, Flink 1.20)
  datasets.music.lastfm            JobManager + 1 TaskManager
  cdc.musicbrainz.public.cdc_demo  SQL Gateway (interactive) + FlinkSessionJob SQL-runner (GitOps)
  datasets.health.brfss                     │
                                            ├─► Iceberg / Nessie catalog (same warehouse as Trino/dbt) ─► Trino/Superset/DataHub
                                            └─► Redpanda topics (analytics.*)
```

- **Operator:** Flink Kubernetes Operator (Argo helm app). Requires cert-manager for its admission webhook (verify/install).
- **Cluster:** `FlinkDeployment` (session mode). Custom image = `flink:1.20` + iceberg-flink-runtime + flink-sql-connector-kafka + avro-confluent/debezium formats.
- **Ingress:** JobManager web UI at `flink.weyland.lab` (Keycloak forward-auth).
- **GitOps:** all under `k8s/data-mesh/flink/`; Argo app.

## The 4 jobs

1. **RTA — trending** (Flink SQL): source `datasets.music.lastfm` (`avro-confluent`) → hopping window of plays + distinct listeners per artist → **append** Iceberg `analytics.trending_artists`.
2. **CDC → lakehouse** (Flink SQL): source `cdc.musicbrainz.public.cdc_demo` (`debezium-avro-confluent`) → **upsert** (PK, Iceberg v2 equality-deletes) `datasets_music.cdc_demo_live`.
3. **Java DataStream (health)**: keyed stateful over `datasets.health.brfss` (per-state running risk, keyed by state) → topic `analytics.health.state_risk`. Java ↔ health.
4. **PyFlink (music)**: Python UDF over `datasets.music.lastfm` (bucket play-count → popularity tier) → sink. Python ↔ music.

## Observability & job history (added — the gap that made the RTA job vanish)

**Problem:** a Flink JobManager keeps *finished* jobs only in an in-memory job store
(`jobstore.expiration-time` default **1h**, `jobstore.max-capacity`), and that store is wiped on **any JM
restart**. Kubernetes HA persists *running* jobs for recovery — **not** completed-job history. So a bounded job
that finishes, or anything predating a JM bounce, disappears with nothing to investigate. Two mechanisms cover the
two halves, and we only had the first:

- **Running work survives restarts** → declarative `FlinkSessionJob` + Kubernetes HA (already planned; also the
  reason the imperative `flink run` RTA submit vanished — it was neither declarative nor persistent).
- **Finished work stays investigable** → archiving + History Server (this addition).

### Archiving + History Server
- FlinkDeployment `flinkConfiguration`: `jobmanager.archive.fs.dir: s3://warehouse/_flink/completed-jobs`. On
  completion the JM writes a self-contained archive (job graph, config, exceptions, per-vertex metrics) to MinIO.
- **History Server** — a standalone Deployment (NOT operator-managed): image `weyland-flink:local` running
  `bin/historyserver.sh start-foreground`; config `historyserver.archive.fs.dir: s3://warehouse/_flink/completed-jobs`,
  `historyserver.archive.fs.refresh-interval: 10000`, `historyserver.web.port: 8082`; `AWS_*` from `nessie-secret`;
  sidecar OFF; ingress **`flink-history.weyland.lab`** (forward-auth). It scans the archive dir and serves **all**
  completed jobs, forever, **independent of the session cluster** — survives JM restarts and session churn.
- **Workflow:** live jobs + slots/tasks → JM UI `flink.weyland.lab`; completed/historical → `flink-history.weyland.lab`.

### Metrics reporter (runtime time-series — IN scope now)
- Prometheus reporter on JM **and** TM. Image carries `flink-metrics-prometheus` (ship from `/opt/flink/opt` → lib).
  `flinkConfiguration`: `metrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory`,
  `metrics.reporter.prom.port: 9249`. Exposes `/metrics` on 9249 (throughput, checkpoint duration, backpressure,
  watermark lag). A `Service` + `ServiceMonitor` (or scrape annotations) wires it into the monitoring stack —
  verify a Prometheus/ServiceMonitor consumer exists under `k8s/monitoring/`; if none yet, the endpoint is live and
  ready to scrape when it lands.

## Deferred (explicit)

RTA live-topic (Iceberg-only now) · KEDA scale-to-zero · Flink→DataHub OpenLineage (like dbt was, until later).

## Build order (validation gate at each step)

1. Flink Operator (+ cert-manager if missing) → operator healthy. **[DONE]**
2. Session cluster + Nessie/Iceberg catalog + MinIO checkpoints → cluster up, `flink.weyland.lab` UI, catalog reachable. **[DONE]**
2a. **Add to the cluster: archive dir (`jobmanager.archive.fs.dir`) + Prometheus reporter (`:9249`)** → `/metrics` live; finished jobs archive to MinIO.
2b. **History Server** deployment + `flink-history.weyland.lab` → completed jobs persist and are browsable across restarts.
2c. **Metrics Service + ServiceMonitor** (or annotations) → scraped by the monitoring stack.
3. Job 1 (RTA) submitted **as a declarative `FlinkSessionJob`** (persists across restarts; re-produce lastfm first) → `analytics.trending_artists` populates, queryable in Trino, job visible + archived on finish.
4. Job 2 (CDC SQL) as `FlinkSessionJob` → `cdc_demo_live` mirrors DB changes.
5. Jobs 3 & 4 (Java + PyFlink) → both surfaces proven.
6. Runbook `flink.md` + `flow-flink.md` diagram; catalog check.
