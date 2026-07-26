#!/usr/bin/env python3
"""B100 P4 follow-on — the gateway eval LEADERBOARD (mlflow.genai.evaluate over registered assets).

Scores every gateway model (minus the judge) against the **registered judge panel** + **registered dataset** — both
live in the `gateway-eval` experiment (run `scripts/register_eval_assets.py` first). One MLflow run per model, all in
the one experiment → a B84-style model comparison, native in MLflow (Experiments → gateway-eval → compare runs). The
model-under-test AND the judges both go through the gateway's OpenAI-compat surface, so NO API keys here.

Run in the mlflow pod (has mlflow.genai; gateway + tracking on localhost):
  kubectl -n weyland exec -i deploy/mlflow -- python < scripts/eval_gateway_models.py
Limit models with GATEWAY_EVAL_MODELS=ollama-gpt-oss-20b,openai-gpt-5-mini (default: all except the judge).
"""
import json
import os
import urllib.request as u

import mlflow
import mlflow.genai as G
from mlflow.genai import evaluate

GW = os.environ.get("GATEWAY_OPENAI_BASE", "http://localhost:5000/gateway/mlflow/v1")
# Guarded gateway calls add judge round-trips per request, so give predict_fn plenty of headroom. Do NOT set
# MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION — it skips creating the trace the scorers read (eval_item.trace is None).
PREDICT_TIMEOUT = int(os.environ.get("GATEWAY_EVAL_TIMEOUT", "600"))
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
# The judges call `openai:/ollama-qwen25-7b` — route it through the gateway. No real key (the gateway holds them).
os.environ["OPENAI_BASE_URL"] = GW
os.environ["OPENAI_API_BASE"] = GW
os.environ.setdefault("OPENAI_API_KEY", "gateway")

EXP = os.environ.get("EVAL_ASSETS_EXPERIMENT", "gateway-eval")
DATASET = os.environ.get("EVAL_DATASET_NAME", "weyland-gateway-eval")
JUDGE_ENDPOINT = os.environ.get("GATEWAY_JUDGE_ENDPOINT", "ollama-qwen25-7b")  # excluded from eval (it's the judge)

_all = [e["name"] for e in json.loads(
    u.urlopen("http://localhost:5000/api/3.0/mlflow/gateway/endpoints/list", timeout=15).read())["endpoints"]]
_sel = os.environ.get("GATEWAY_EVAL_MODELS")
MODELS = [m.strip() for m in _sel.split(",") if m.strip()] if _sel else [e for e in _all if e != JUDGE_ENDPOINT]


def _make_predict(model_name):
    def predict(question: str) -> str:
        body = json.dumps({"model": model_name, "messages": [{"role": "user", "content": question}]}).encode()
        req = u.Request(f"{GW}/chat/completions", data=body, method="POST", headers={"Content-Type": "application/json"})
        with u.urlopen(req, timeout=PREDICT_TIMEOUT) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"] or ""
    return predict


def main():
    exp = mlflow.set_experiment(EXP)
    scorers = G.list_scorers(experiment_id=exp.experiment_id)
    if not scorers:
        raise SystemExit(f"No registered judges in '{EXP}'. Run scripts/register_eval_assets.py first.")
    data = G.get_dataset(name=DATASET)  # the registered golden dataset
    print(f"experiment={EXP}({exp.experiment_id})  judges={[s.name for s in scorers]}  dataset={DATASET}  models={len(MODELS)}\n", flush=True)
    for model in MODELS:
        print(f"== {model} ==", flush=True)
        try:
            with mlflow.start_run(run_name=model):
                res = evaluate(data=data, scorers=scorers, predict_fn=_make_predict(model))
                agg = {k: round(v, 3) for k, v in res.metrics.items() if isinstance(v, (int, float))}
                print(f"   {agg}", flush=True)
        except Exception as exc:
            import traceback
            print(f"   FAILED: {type(exc).__name__}: {str(exc)[:220]}", flush=True)
            traceback.print_exc()
    print(f"\ndone — Experiments -> {EXP} -> compare the runs (one per model, same judges + dataset).", flush=True)


if __name__ == "__main__":
    main()
