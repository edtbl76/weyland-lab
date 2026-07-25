#!/usr/bin/env python3
"""B84 P2b spike — MLflow GenAI evaluation (single-judge LLM-as-judge) head-to-head vs the 3-judge panel.

Reads the latest scored eval run's per-(model, question) answer + retrieved context from Postgres, runs
`mlflow.evaluate` with GenAI metrics (faithfulness + answer_relevance), judge = a local Ollama model via the
OpenAI-compat shim, and logs one MLflow run per model to the `mlflow_evaluate` experiment. Then compare its per-model
scores to the panel's (`weyland_rag_eval`) — SAME golden set, DIFFERENT judging mechanism (1 judge vs a >=3 panel).

Run (no rebuild — the dagster-user-code pod has mlflow + psycopg2 + WEYLAND_PG/MLFLOW/OLLAMA env):
  kubectl -n weyland exec -i deploy/dagster-user-code -- python < scripts/eval_mlflow_evaluate.py
"""
import json
import os

import mlflow
import pandas as pd
import psycopg2
from mlflow.metrics.genai import answer_relevance, faithfulness

# Spike dep: `mlflow.evaluate`'s default evaluator renders plots via matplotlib, which the dagster image lacks.
# Install it at runtime for this one-off (ephemeral — not baked into the image). NOTE: `mlflow.evaluate` + these
# genai metrics are DEPRECATED since MLflow 3.4 — the modern path is `mlflow.genai.evaluate`; this spike uses the
# legacy path only because its Ollama-judge wiring is a known quantity. Adoption would move to `mlflow.genai.evaluate`.
import subprocess  # noqa: E402
import sys  # noqa: E402
try:
    import matplotlib  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "matplotlib"], check=False)

# Judge = a local Ollama model via the OpenAI-compat endpoint. MLflow's genai metrics use the `openai` provider, which
# respects these env vars — so the judge runs on-LAN, $0 (no cloud key).
_OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
os.environ["OPENAI_API_BASE"] = _OLLAMA
os.environ["OPENAI_BASE_URL"] = _OLLAMA
os.environ.setdefault("OPENAI_API_KEY", "ollama")
JUDGE = os.environ.get("EVAL_MLFLOW_JUDGE", "openai:/gpt-oss:20b")

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000"))
mlflow.set_experiment("mlflow_evaluate")


def _ctx(raw) -> str:
    """Join the retrieved chunks into a context string (same shape the panel judge consumes)."""
    try:
        chunks = raw if isinstance(raw, list) else json.loads(raw)
    except Exception:
        return str(raw)[:8000]
    return "\n\n".join((c.get("content", "") if isinstance(c, dict) else str(c)) for c in (chunks or []))[:8000]


conn = psycopg2.connect(
    host=os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local"),
    port=os.environ.get("WEYLAND_PG_PORT", "5432"),
    dbname=os.environ.get("WEYLAND_PG_DB", "weyland"),
    user=os.environ.get("WEYLAND_PG_USER", "weyland"),
    password=os.environ.get("WEYLAND_PG_PASSWORD", ""),
)
with conn, conn.cursor() as cur:
    cur.execute("SELECT id FROM eval_runs WHERE status='scored' ORDER BY id DESC LIMIT 1")
    run_id = cur.fetchone()[0]
    cur.execute(
        "SELECT er.model, eq.question, er.contexts, er.answer "
        "FROM eval_results er JOIN eval_questions eq ON eq.id = er.question_id "
        "WHERE er.run_id = %s AND er.error IS NULL ORDER BY er.model, eq.id",
        (run_id,),
    )
    rows = cur.fetchall()
conn.close()

by_model: dict = {}
for model, question, contexts, answer in rows:
    by_model.setdefault(model, []).append({"inputs": question, "context": _ctx(contexts), "answer": answer or ""})

print(f"eval run {run_id}: {len(by_model)} models, judge={JUDGE}", flush=True)
metrics = [faithfulness(model=JUDGE), answer_relevance(model=JUDGE)]
for model, records in by_model.items():
    df = pd.DataFrame(records)
    try:
        with mlflow.start_run(run_name=f"mlflow-eval-run{run_id}-{model}"):
            mlflow.set_tags({"eval_run_id": str(run_id), "model": model, "judge": JUDGE, "source": "mlflow.evaluate"})
            res = mlflow.evaluate(data=df, predictions="answer", extra_metrics=metrics, evaluators="default")
            agg = {k: round(v, 3) for k, v in res.metrics.items() if isinstance(v, (int, float))}
            print(f"  {model}: {agg}", flush=True)
    except Exception as exc:
        print(f"  {model}: FAILED — {exc}", flush=True)

print("done — compare the `mlflow_evaluate` runs vs the panel's `weyland_rag_eval` on the same golden set.", flush=True)
