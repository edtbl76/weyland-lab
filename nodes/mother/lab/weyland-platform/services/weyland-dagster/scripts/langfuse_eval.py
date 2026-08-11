"""B103 eval — seed the Langfuse `weyland-golden` dataset from the B96 golden question set.

Mirrors `weyland_pipeline/golden_questions.json` (the pinned 20q: 10 conceptual + 10 lexical) into a Langfuse **Dataset**
so the OFFLINE lane (B84 MLflow judge-panel) and the ONLINE lane (Langfuse evaluators/experiments) share the SAME
fixtures. Reference-free (question-only, like B84): each item carries the question as `input` + a `question_type`
metadata tag so you can slice the conceptual-vs-lexical contrast the golden set was built to measure.

Idempotent: deterministic item ids (sha1 of the question) → re-runs upsert, never duplicate. Langfuse **REST** via httpx
(Basic auth pk/sk) — NO langfuse SDK (its `packaging<26` pin conflicts with the dagster lockfile, same reason as
`sync_prompts.py`). Creds: `LANGFUSE_HOST` + `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` on the user-code pod.

Run: `kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/langfuse_eval.py`
(or materialize the `langfuse_golden_dataset` asset in the Dagster `registrations` group).
"""
import hashlib
import json
import os
import pathlib

import httpx

HOST = os.environ["LANGFUSE_HOST"].rstrip("/")
AUTH = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
DATASET = "weyland-golden"
_GOLDEN = pathlib.Path(__file__).resolve().parent.parent / "weyland_pipeline" / "golden_questions.json"


def ensure_dataset(c: httpx.Client) -> None:
    """Create the dataset if absent (GET 404 → POST). Langfuse has no dataset-upsert, so guard on existence."""
    if c.get(f"/api/public/v2/datasets/{DATASET}").status_code == 200:
        return
    c.post("/api/public/v2/datasets", json={
        "name": DATASET,
        "description": "B96 golden eval set (10 conceptual + 10 lexical), mirrored from golden_questions.json. Shared "
                       "fixtures for the offline (B84 MLflow judge-panel) and online (Langfuse) eval lanes. "
                       "Reference-free — judged, not string-matched.",
        "metadata": {"source": "golden_questions.json", "backlog": "B96/B103"},
    }).raise_for_status()


def seed_items(c: httpx.Client) -> int:
    """Upsert the 20 golden questions as dataset items (deterministic id → idempotent). Input matches the tool-server
    `/context/ask` contract so the experiment runner can POST an item straight to the RAG."""
    qs = json.loads(_GOLDEN.read_text())["questions"]
    for item in qs:
        q, qtype = item["q"], item["type"]
        c.post("/api/public/dataset-items", json={
            "id": "golden-" + hashlib.sha1(q.encode()).hexdigest()[:16],   # deterministic → upsert, no dupes
            "datasetName": DATASET,
            "input": {"query": q, "backend": "pgvector"},
            "metadata": {"question_type": qtype},   # slice conceptual vs lexical (the B96 contrast)
        }).raise_for_status()
    return len(qs)


def main() -> None:
    with httpx.Client(base_url=HOST, auth=AUTH, timeout=30) as c:
        ensure_dataset(c)
        n = seed_items(c)
    print(f"Langfuse dataset '{DATASET}': {n} items upserted (from golden_questions.json)")


if __name__ == "__main__":
    main()
