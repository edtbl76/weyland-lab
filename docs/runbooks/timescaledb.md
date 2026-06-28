# TimescaleDB — Time-Series Store (B65 Tier-2)

**What:** Dedicated TimescaleDB instance (`timescale/timescaledb-ha:pg16`) in ns `data-mesh`. TimescaleDB is a Postgres extension for time-series — hypertables, continuous aggregates, retention policies. Separate from `weyland-postgres` to isolate time-series workloads. UI at `grafana.weyland.lab` (TimescaleDB datasource) and `superset.weyland.lab` (TimescaleDB database connection).

---

## Hypertables

| Table | Source | Dagster asset |
|---|---|---|
| `eval_scores_ts` | `eval_scores` (weyland Postgres) | `ts_eval_scores` |
| `guardrail_verdicts_ts` | `guardrail_verdicts` (weyland Postgres) | `ts_guardrail_verdicts` |
| `dagster_run_durations` | `dagster.runs` (dagster Postgres) | `ts_dagster_runs` |
| `unleash_feature_metrics` | `client_metrics_env` (unleash Postgres) | `ts_unleash_metrics` |
| `datahub_ingestion_runs` | DataHub GMS GraphQL API | `ts_datahub_ingestion` |

Scheduled hourly via `weyland_timeseries_schedule` / `weyland_timeseries_job`.

---

## Connect

- **IntelliJ / DataGrip:** IntelliJ Kubernetes plugin → Services → data-mesh → timescaledb → Forward Ports → 5432. DataGrip "PostgreSQL" datasource: host `localhost`, port `5432`, db `timeseries`, user `weyland`, password `weyland_dev_password`.
- **Grafana:** datasource "TimescaleDB" (PostgreSQL type, `timescaledb.data-mesh.svc.cluster.local:5432`, db `timeseries`, TimescaleDB toggle ON).
- **Superset:** database connection `postgresql+psycopg2://weyland:weyland_dev_password@timescaledb.data-mesh.svc.cluster.local:5432/timeseries`.
- **In-cluster (Dagster/other pods):** `timescaledb.data-mesh.svc.cluster.local:5432`.

---

## Deploy

GitOps: `k8s/data-mesh/timescaledb.yaml` (PVC + Deployment + Service + `TimescaleDBDown` PrometheusRule). Push → Argo syncs.

**Imperative secret (not in git — recreate after cluster rebuild):**
```
kubectl -n data-mesh create secret generic timescaledb-secret --from-literal=POSTGRES_USER=weyland --from-literal=POSTGRES_PASSWORD=weyland_dev_password --from-literal=POSTGRES_DB=timeseries
```

**Initialize extension + hypertables (one-time):**
```
kubectl -n data-mesh exec deploy/timescaledb -- psql -U weyland -d timeseries -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
```
```
kubectl -n data-mesh exec deploy/timescaledb -- psql -U weyland -d timeseries -c "
CREATE TABLE IF NOT EXISTS eval_scores_ts (time TIMESTAMPTZ NOT NULL, run_id INT, model TEXT, metric TEXT, judge TEXT, score FLOAT);
SELECT create_hypertable('eval_scores_ts','time', if_not_exists => TRUE);
CREATE TABLE IF NOT EXISTS guardrail_verdicts_ts (time TIMESTAMPTZ NOT NULL, validator TEXT, hook TEXT, decision TEXT, actor TEXT, latency_ms FLOAT);
SELECT create_hypertable('guardrail_verdicts_ts','time', if_not_exists => TRUE);
CREATE TABLE IF NOT EXISTS dagster_run_durations (time TIMESTAMPTZ NOT NULL, pipeline_name TEXT, status TEXT, duration_seconds FLOAT, run_id TEXT);
SELECT create_hypertable('dagster_run_durations','time', if_not_exists => TRUE);
CREATE TABLE IF NOT EXISTS unleash_feature_metrics (time TIMESTAMPTZ NOT NULL, feature_name TEXT, environment TEXT, yes INT, no INT);
SELECT create_hypertable('unleash_feature_metrics','time', if_not_exists => TRUE);
CREATE TABLE IF NOT EXISTS datahub_ingestion_runs (time TIMESTAMPTZ NOT NULL, source_type TEXT, source_name TEXT, status TEXT, duration_seconds FLOAT, records_written INT);
SELECT create_hypertable('datahub_ingestion_runs','time', if_not_exists => TRUE);
"
```

---

## Gotchas

1. **DataHub GraphQL `lastExecRequest` undefined** — field name changed in DataHub 1.6.0. Correct schema: `executions(start:0,count:1) { executionRequests { id result { status startTimeMs durationMs } } }`. Introspect with `__type(name:"IngestionSource") { fields { name } }` to verify.

2. **DataHub GraphQL returns empty without auth** — the query works in-cluster from the Dagster pod (has `DATAHUB_GMS_TOKEN` env). Raw curl from mother's host shell returns empty (GMS not reachable on host network). Always test GraphQL from inside the Dagster pod: `kubectl -n weyland exec deploy/dagster-user-code -- python3 -c "..."`.

3. **Unleash `client_metrics_env` is empty** — no feature flag traffic recorded yet; table stays empty until Unleash gets real usage. Expected.

4. **`max_connections=200`** set via args — Postgres default (100) exhausted by DataHub profiling running parallel connections across all DBs. TimescaleDB starts with 200 for headroom.

---

## Monitoring

- `TimescaleDBDown` PrometheusRule in `k8s/data-mesh/timescaledb.yaml`
- DataHub: `emit_timescaledb` in `datahub_catalog_emit_job` (hourly) — 5 hypertables cataloged as `timescaledb` platform datasets with lineage ← source Postgres tables.
- Grafana: datasource registered; dashboards pending (B69).
- Superset: 10 charts built (eval trends, guardrail trends, Dagster run health, DataHub ingestion runs).
