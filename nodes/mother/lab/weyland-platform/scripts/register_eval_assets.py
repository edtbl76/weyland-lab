#!/usr/bin/env python3
"""B100 P4 follow-on — register reusable eval assets: a JUDGE PANEL + a golden DATASET (mlflow.genai).

Populates the AI Gateway's **Judges** + **Datasets** tabs with governed, reusable artifacts (vs the inline
scorers/questions in eval_gateway_models.py). The judges score via the local `ollama-qwen25-7b` gateway endpoint
(no quota, on-LAN). Idempotent. Run in the mlflow pod (has mlflow.genai; gateway + tracking on localhost, no keys):
  kubectl -n weyland exec -i deploy/mlflow -- python < scripts/register_eval_assets.py
"""
import os

import mlflow
import mlflow.genai as G

GW = os.environ.get("GATEWAY_OPENAI_BASE", "http://localhost:5000/gateway/mlflow/v1")
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
# Judge = the local qwen2.5:7b endpoint via the gateway's OpenAI-compat surface. No real key (gateway holds them).
os.environ["OPENAI_BASE_URL"] = GW
os.environ["OPENAI_API_BASE"] = GW
os.environ.setdefault("OPENAI_API_KEY", "gateway")
JUDGE = os.environ.get("GATEWAY_EVAL_JUDGE", "openai:/ollama-qwen25-7b")
# Dedicated eval home (created if absent) — NOT Default. Judges/datasets are eval-run properties, not per-model, so
# they live in one comparison experiment, not the 15 per-endpoint `gateway/<name>` ones.
EXP = mlflow.set_experiment(os.environ.get("EVAL_ASSETS_EXPERIMENT", "gateway-eval")).experiment_id

# Reusable lab judges (reference-free: score {{ inputs }} + {{ outputs }}, no gold answer needed).
JUDGES = [
    ("weyland-relevance",
     "Does the response {{ outputs }} directly and correctly address the request {{ inputs }}? "
     "Answer 'yes' if it is on-topic and correct, 'no' if it is off-topic, evasive, or wrong."),
    ("weyland-conciseness",
     "Given the request {{ inputs }}, is the response {{ outputs }} concise and free of filler, repetition, or "
     "padding? Answer 'yes' if concise, 'no' if bloated."),
    ("weyland-honesty",
     "For request {{ inputs }} and response {{ outputs }}: if the answer isn't known, does it say so plainly "
     "rather than fabricate? Answer 'yes' if honest (a correct answer OR an honest 'I don't know'), 'no' if it "
     "fabricates a confident but unsupported answer."),
]

DATASET = os.environ.get("EVAL_DATASET_NAME", "weyland-gateway-eval")
RECORDS = [
    {"inputs": {"question": "In two sentences, what is a data lakehouse and why would you use one?"}, "expectations": {"kind": "conceptual"}},
    {"inputs": {"question": "Explain the difference between OLTP and OLAP workloads."}, "expectations": {"kind": "conceptual"}},
    {"inputs": {"question": "Briefly, what is retrieval-augmented generation and when does it help?"}, "expectations": {"kind": "conceptual"}},
    {"inputs": {"question": "Write a Python function that returns the nth Fibonacci number iteratively."}, "expectations": {"kind": "code"}},
    {"inputs": {"question": "In SQL, how do you select the second-highest salary from an employees table?"}, "expectations": {"kind": "code"}},
    {"inputs": {"question": "Write a Python one-liner that flattens a list of lists."}, "expectations": {"kind": "code"}},
]


def register_judges():
    try:
        existing = {s.name for s in G.list_scorers(experiment_id=EXP)}
    except Exception:
        existing = set()
    for name, instr in JUDGES:
        if name in existing:
            print(f"  judge exists: {name}")
            continue
        try:
            G.make_judge(name=name, instructions=instr, model=JUDGE).register(experiment_id=EXP)
            print(f"  registered judge: {name}")
        except Exception as e:
            print(f"  judge {name} FAILED: {type(e).__name__}: {str(e)[:220]}")


def register_dataset():
    try:
        if G.get_dataset(name=DATASET) is not None:
            print(f"  dataset exists: {DATASET}")
            return
    except Exception:
        pass
    try:
        ds = G.create_dataset(name=DATASET, experiment_id=EXP)
        ds.merge_records(RECORDS)
        print(f"  created dataset: {DATASET} ({len(RECORDS)} records)")
    except Exception as e:
        print(f"  dataset {DATASET} FAILED: {type(e).__name__}: {str(e)[:220]}")


def cleanup_default(exp_id):
    """Move the eval judges + dataset out of Default (experiment 0) into the dedicated experiment (idempotent)."""
    for name, _ in JUDGES:
        try:
            G.delete_scorer(name=name, experiment_id="0")
            print(f"  cleaned judge from Default: {name}")
        except Exception:
            pass
    try:
        ds = G.get_dataset(name=DATASET)
        if exp_id not in (ds.experiment_ids or []):
            G.delete_dataset(name=DATASET)
            print(f"  cleaned dataset from {ds.experiment_ids}: {DATASET}")
    except Exception:
        pass


print(f"judge={JUDGE}  experiment=gateway-eval ({EXP})")
cleanup_default(EXP)
register_judges()
register_dataset()
print("done — Experiments -> gateway-eval -> Judges / Datasets")
