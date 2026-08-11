"""B103 eval — mirror the git eval-fixture SSOT (`weyland_pipeline/eval_sets/*.json`) into Langfuse Datasets.

The single source of truth is **git**: each set is one JSON in `eval_sets/` (`{name, description, questions:[{type,q}]}`).
This mirrors every set to a Langfuse Dataset `weyland-<name>` (weyland-golden, weyland-regression, …) so the offline
(B84 MLflow judge-panel) and online (Langfuse) eval lanes share the SAME fixtures. Langfuse holds a COPY, never the
source — a Langfuse DB reset is rebuilt by re-running this. Reference-free (question-only, like B84): item input = the
question, `metadata.question_type` = conceptual/lexical/functional/negative.

Idempotent: deterministic item ids (per dataset+question) → re-runs upsert, no dupes. Langfuse **REST** via httpx (Basic
auth pk/sk) — NO langfuse SDK (its `packaging<26` pin conflicts with the dagster lockfile). Env: LANGFUSE_HOST +
LANGFUSE_PUBLIC_KEY/SECRET_KEY. Run: `kubectl -n weyland exec deploy/dagster-user-code -- python
/app/scripts/langfuse_eval.py` (or the `langfuse_golden_dataset` registrations asset).
"""
import hashlib
import json
import os
import pathlib

import httpx

HOST = os.environ["LANGFUSE_HOST"].rstrip("/")
AUTH = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
EVAL_SETS = pathlib.Path(__file__).resolve().parent.parent / "weyland_pipeline" / "eval_sets"


def ensure_dataset(c: httpx.Client, name: str, description: str) -> None:
    if c.get(f"/api/public/v2/datasets/{name}").status_code == 200:
        return
    c.post("/api/public/v2/datasets", json={
        "name": name, "description": description,
        "metadata": {"source": "git weyland_pipeline/eval_sets/", "backlog": "B96/B103"},
    }).raise_for_status()


def seed(c: httpx.Client, dataset: str, questions: list) -> int:
    for item in questions:
        q, qtype = item["q"], item["type"]
        c.post("/api/public/dataset-items", json={
            "id": "es-" + hashlib.sha1(f"{dataset}:{q}".encode()).hexdigest()[:16],   # deterministic → upsert
            "datasetName": dataset,
            "input": {"query": q, "backend": "pgvector"},   # matches the tool-server /context/ask contract
            "metadata": {"question_type": qtype},
        }).raise_for_status()
    return len(questions)


def main() -> None:
    with httpx.Client(base_url=HOST, auth=AUTH, timeout=30) as c:
        total = 0
        for path in sorted(EVAL_SETS.glob("*.json")):
            data = json.loads(path.read_text())
            dataset = f"weyland-{data['name']}"
            ensure_dataset(c, dataset, data.get("description", f"weyland eval set: {data['name']}"))
            n = seed(c, dataset, data["questions"])
            total += n
            print(f"  {dataset}: {n} items upserted (from {path.name})")
    print(f"eval-fixture SSOT → Langfuse Datasets: {total} items across the eval_sets/ catalog")


if __name__ == "__main__":
    main()
