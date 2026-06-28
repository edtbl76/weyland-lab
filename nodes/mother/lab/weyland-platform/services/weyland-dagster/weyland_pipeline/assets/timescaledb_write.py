"""B65 Tier-2 — TimescaleDB time-series writes.

Pulls temporal data from 5 in-cluster sources and upserts into TimescaleDB hypertables.
Idempotent: uses INSERT ... ON CONFLICT DO NOTHING where a natural key exists, or
truncate-and-reload for aggregated snapshots. Runs on the same schedule as the main
ingestion job.

Hypertables:
  eval_scores_ts         ← eval_scores (weyland Postgres)
  guardrail_verdicts_ts  ← guardrail_verdicts (weyland Postgres)
  dagster_run_durations  ← Dagster run history (Dagster Postgres)
  unleash_feature_metrics← client_metrics_env (unleash Postgres)
  datahub_ingestion_runs ← DataHub GMS execution API
"""
import os
import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from dagster import asset, Output, MetadataValue


def _tsdb_conn():
    return psycopg2.connect(
        host=os.environ.get("TIMESCALEDB_HOST", "timescaledb.data-mesh.svc.cluster.local"),
        port=int(os.environ.get("TIMESCALEDB_PORT", "5432")),
        dbname=os.environ.get("TIMESCALEDB_DB", "timeseries"),
        user=os.environ.get("TIMESCALEDB_USER", "weyland"),
        password=os.environ.get("TIMESCALEDB_PASSWORD", "weyland_dev_password"),
    )


def _weyland_conn():
    return psycopg2.connect(
        host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
        port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
        dbname="weyland",
        user=os.environ.get("WEYLAND_PG_USER", "weyland"),
        password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
    )


def _dagster_conn():
    return psycopg2.connect(
        host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
        port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
        dbname="dagster",
        user=os.environ.get("WEYLAND_PG_USER", "weyland"),
        password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
    )


def _unleash_conn():
    return psycopg2.connect(
        host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
        port=int(os.environ.get("WEYLAND_PG_PORT", "5432")),
        dbname="unleash",
        user=os.environ.get("WEYLAND_PG_USER", "weyland"),
        password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
    )


@asset(group_name="timeseries", description="Sync eval_scores → TimescaleDB hypertable eval_scores_ts")
def ts_eval_scores():
    src = _weyland_conn()
    dst = _tsdb_conn()
    try:
        with src.cursor() as cur:
            cur.execute("""
                SELECT es.created_at, run.id, run.status, es.judge, es.metric, es.score
                FROM eval_scores es
                JOIN eval_results er ON es.result_id = er.id
                JOIN eval_runs run ON er.run_id = run.id
                WHERE es.created_at IS NOT NULL
                ORDER BY es.created_at DESC
                LIMIT 10000
            """)
            rows = cur.fetchall()
        with dst.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO eval_scores_ts (time, run_id, model, metric, judge, score)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, [(r[0], r[1], r[2], r[4], r[3], r[5]) for r in rows])
            dst.commit()
        return Output(len(rows), metadata={"rows": MetadataValue.int(len(rows))})
    finally:
        src.close()
        dst.close()


@asset(group_name="timeseries", description="Sync guardrail_verdicts → TimescaleDB hypertable guardrail_verdicts_ts")
def ts_guardrail_verdicts():
    src = _weyland_conn()
    dst = _tsdb_conn()
    try:
        with src.cursor() as cur:
            cur.execute("""
                SELECT created_at, validator, hook, decision, actor, latency_ms
                FROM guardrail_verdicts
                WHERE created_at IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 50000
            """)
            rows = cur.fetchall()
        with dst.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO guardrail_verdicts_ts (time, validator, hook, decision, actor, latency_ms)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows)
            dst.commit()
        return Output(len(rows), metadata={"rows": MetadataValue.int(len(rows))})
    finally:
        src.close()
        dst.close()


@asset(group_name="timeseries", description="Sync Dagster run history → TimescaleDB hypertable dagster_run_durations")
def ts_dagster_runs():
    src = _dagster_conn()
    dst = _tsdb_conn()
    try:
        with src.cursor() as cur:
            cur.execute("""
                SELECT
                    to_timestamp(start_time) AS time,
                    pipeline_name,
                    status,
                    CASE WHEN end_time IS NOT NULL AND start_time IS NOT NULL
                         THEN end_time - start_time ELSE NULL END AS duration_seconds,
                    run_id
                FROM runs
                WHERE start_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT 10000
            """)
            rows = cur.fetchall()
        with dst.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO dagster_run_durations (time, pipeline_name, status, duration_seconds, run_id)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows)
            dst.commit()
        return Output(len(rows), metadata={"rows": MetadataValue.int(len(rows))})
    finally:
        src.close()
        dst.close()


@asset(group_name="timeseries", description="Sync Unleash feature metrics → TimescaleDB hypertable unleash_feature_metrics")
def ts_unleash_metrics():
    src = _unleash_conn()
    dst = _tsdb_conn()
    try:
        with src.cursor() as cur:
            cur.execute("""
                SELECT timestamp, feature_name, environment, yes, no
                FROM client_metrics_env
                WHERE timestamp IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 100000
            """)
            rows = cur.fetchall()
        with dst.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO unleash_feature_metrics (time, feature_name, environment, yes, no)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows)
            dst.commit()
        return Output(len(rows), metadata={"rows": MetadataValue.int(len(rows))})
    finally:
        src.close()
        dst.close()


@asset(group_name="timeseries", description="Sync DataHub ingestion run history → TimescaleDB hypertable datahub_ingestion_runs")
def ts_datahub_ingestion():
    import requests as req_lib

    gms = os.environ.get("DATAHUB_GMS_URL", "http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080")
    token = os.environ.get("DATAHUB_GMS_TOKEN", "")
    dst = _tsdb_conn()
    rows = []
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = req_lib.post(
            f"{gms}/api/graphql",
            json={"query": """
                { listIngestionSources(input:{count:50, start:0}) {
                    total
                    ingestionSources {
                        urn type
                        lastExecRequest {
                            id status
                            result { startTimeMs durationMs numSucceeded numFailed }
                        }
                    }
                } }
            """},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        gql_data = data.get("data") or {}
        sources = (gql_data.get("listIngestionSources") or {}).get("ingestionSources") or []
        for s in sources:
            exec_req = s.get("lastExecRequest") or {}
            result = exec_req.get("result") or {}
            start_ms = result.get("startTimeMs")
            if not start_ms:
                continue
            rows.append((
                datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc),
                s.get("type", "unknown"),
                s.get("urn", ""),
                exec_req.get("status", "unknown"),
                (result.get("durationMs") or 0) / 1000.0,
                (result.get("numSucceeded") or 0),
            ))
        with dst.cursor() as cur:
            psycopg2.extras.execute_values(cur, """
                INSERT INTO datahub_ingestion_runs (time, source_type, source_name, status, duration_seconds, records_written)
                VALUES %s
                ON CONFLICT DO NOTHING
            """, rows)
            dst.commit()
        return Output(len(rows), metadata={"rows": MetadataValue.int(len(rows))})
    finally:
        dst.close()
