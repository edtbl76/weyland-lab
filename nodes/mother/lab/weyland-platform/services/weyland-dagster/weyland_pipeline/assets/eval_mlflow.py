"""B4 eval — log per-model eval metrics to MLflow as experiment runs (then DataHub catalogs them).

After eval_scores writes the judge-panel scores, aggregate per-model average metrics + latency for
the latest scored run and log one MLflow run per model under the `weyland_rag_eval` experiment. This
is MLflow's real use (experiment tracking, not a registry dump) and gives DataHub model/run/metric
lineage tied to the eval data product. Metrics/params only — no artifacts — so no S3, just the
tracking URI. Idempotent enough for a lab: re-running logs a fresh run set for the same eval_run_id.
"""
import os
from collections import defaultdict

from dagster import MetadataValue, Output, asset

from weyland_pipeline.resources import PostgresResource


@asset(
    group_name="eval",
    description="Log per-model eval metrics for the latest scored run to MLflow (experiment runs) -> DataHub.",
)
def eval_mlflow_log(context, postgres: PostgresResource, eval_scores: dict) -> Output[dict]:
    import mlflow

    run_id = eval_scores["run_id"]
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT er.model, es.metric, AVG(es.score)
                FROM eval_results er
                JOIN eval_scores es ON es.result_id = er.id
                WHERE er.run_id = %s
                GROUP BY er.model, es.metric
                """,
                (run_id,),
            )
            score_rows = cur.fetchall()
            cur.execute(
                "SELECT model, AVG(latency_ms), COUNT(DISTINCT question_id) "
                "FROM eval_results WHERE run_id = %s GROUP BY model",
                (run_id,),
            )
            meta_rows = cur.fetchall()
            cur.execute(
                "SELECT er.question_id, er.model, "
                "AVG(es.score) FILTER (WHERE es.metric='faithfulness') AS faithfulness, "
                "AVG(es.score) FILTER (WHERE es.metric='answer_relevancy') AS answer_relevancy, "
                "AVG(es.score) FILTER (WHERE es.metric='context_relevancy') AS context_relevancy "
                "FROM eval_results er JOIN eval_scores es ON es.result_id = er.id "
                "WHERE er.run_id = %s GROUP BY er.question_id, er.model ORDER BY er.question_id, er.model",
                (run_id,),
            )
            table_rows = cur.fetchall()

    by_model = defaultdict(dict)
    for model, metric, avg in score_rows:
        by_model[model][metric] = float(avg)
    model_meta = {m: (float(lat) if lat is not None else None, int(q)) for m, lat, q in meta_rows}

    if not by_model:
        context.log.warning(f"eval run {run_id} has no scores — nothing to log to MLflow")
        return Output({"run_id": run_id, "models_logged": 0}, metadata={"models_logged": 0})

    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")
    )
    mlflow.set_experiment("weyland_rag_eval")
    logged = 0
    for model, metrics in by_model.items():
        latency, n_questions = model_meta.get(model, (None, 0))
        with mlflow.start_run(run_name=f"run{run_id}-{model}"):
            mlflow.log_params({"model": model, "eval_run_id": run_id, "num_questions": n_questions})
            mlflow.log_metrics(metrics)
            if latency is not None:
                mlflow.log_metric("latency_ms", latency)
            mlflow.set_tags({"eval_run_id": str(run_id), "source": "weyland-dagster"})
        logged += 1

    # B84 P2a — a per-question eval TABLE on a summary run → MLflow's row-level view (drill into which question each
    # model won/lost, not just the 3 aggregate numbers). Fail-safe: an artifact-store hiccup must not fail the eval.
    try:
        cols = {"question_id": [], "model": [], "faithfulness": [], "answer_relevancy": [], "context_relevancy": []}
        for qid, model, f, a, c in table_rows:
            cols["question_id"].append(qid)
            cols["model"].append(model)
            cols["faithfulness"].append(float(f) if f is not None else None)
            cols["answer_relevancy"].append(float(a) if a is not None else None)
            cols["context_relevancy"].append(float(c) if c is not None else None)
        if cols["question_id"]:
            with mlflow.start_run(run_name=f"run{run_id}-summary"):
                mlflow.set_tags({"eval_run_id": str(run_id), "source": "weyland-dagster", "kind": "summary"})
                mlflow.log_table(data=cols, artifact_file="eval_results.json")
            context.log.info(f"Logged per-question eval table ({len(cols['question_id'])} rows) to MLflow")
    except Exception as exc:
        context.log.warning(f"eval table log skipped: {exc}")

    context.log.info(f"Logged {logged} model runs to MLflow for eval run {run_id}")
    return Output(
        {"run_id": run_id, "models_logged": logged},
        metadata={
            "models_logged": MetadataValue.int(logged),
            "eval_run_id": MetadataValue.int(run_id),
        },
    )
