"""B4 eval — Step 3: run each eval question through each model via the tool-server RAG.

For every (model x question) it calls the tool-server `/context/ask` (retrieve + generate) and
stores the answer + retrieved contexts in eval_results. Model-OUTER loop so each Ollama model
stays resident while it answers all questions (6 model loads, not one per call).

Reuse-only: the tool-server (RAG), Ollama (generation), Postgres (storage). No new infra.
"""
import json
import os
import time

import httpx
from dagster import Output, MetadataValue, asset, get_dagster_logger

from weyland_pipeline.assets.eval_testset import EVAL_MODELS
from weyland_pipeline.resources import PostgresResource

# In-cluster tool-server service (same namespace).
TOOL_SERVER_URL = os.environ.get("TOOL_SERVER_URL", "http://weyland-tool-server:8080")
EVAL_BACKEND = os.environ.get("EVAL_BACKEND", "pgvector")
EVAL_ASK_LIMIT = int(os.environ.get("EVAL_ASK_LIMIT", "3"))


@asset(
    group_name="eval",
    description="Run each eval question through each model via tool-server /context/ask -> eval_results.",
)
def eval_run_matrix(postgres: PostgresResource, eval_testset: dict) -> Output[dict]:
    run_id = eval_testset["run_id"]

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, question FROM eval_questions WHERE run_id = %s ORDER BY id", (run_id,))
            questions = cur.fetchall()  # [(question_id, question_text), ...]

    written, errors = 0, 0
    log = get_dagster_logger()
    # Model-outer keeps each model warm in Ollama across all questions before switching.
    with httpx.Client(timeout=600) as client:
        for model in EVAL_MODELS:
            for question_id, question in questions:
                t0 = time.monotonic()
                answer, contexts, error = None, None, None
                try:
                    resp = client.post(
                        f"{TOOL_SERVER_URL}/context/ask",
                        json={"query": question, "backend": EVAL_BACKEND, "limit": EVAL_ASK_LIMIT, "model": model},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    answer = data.get("answer")
                    contexts = data.get("sources")
                except Exception as e:
                    error = f"{type(e).__name__}: {str(e)[:200]}"
                    # B96 — LOG it. These errors were only ever written to eval_results.error, where nothing read
                    # them: run 8 (2026-07-21) had 117/120 generations fail with 503 and still reported SUCCESS.
                    # First few only, so a dead backend doesn't produce 120 identical tracebacks.
                    if errors <= 5:
                        log.warning(f"/context/ask failed (model={model}, q={question_id}): {error}")
                    errors += 1
                latency_ms = int((time.monotonic() - t0) * 1000)

                # Fresh connection per write so a long run (slow CPU calls) never holds one open
                # across HTTP, and partial progress persists if the asset dies mid-matrix.
                with postgres.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO eval_results "
                            "(run_id, question_id, model, backend, answer, contexts, latency_ms, error) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (
                                run_id,
                                question_id,
                                model,
                                EVAL_BACKEND,
                                answer,
                                json.dumps(contexts) if contexts is not None else None,
                                latency_ms,
                                error,
                            ),
                        )
                written += 1

    # B96 — FAIL LOUDLY on a hollow matrix. Individual generations are allowed to fail (a flaky model call
    # shouldn't sink a 120-cell matrix), but a mostly-failed run must NOT be marked results_ready: downstream
    # scoring filters on `error IS NULL`, so it would happily "succeed" over the handful of survivors and
    # publish a leaderboard built from almost nothing. That is exactly what run 8 did — 117/120 results were
    # `503 Service Unavailable` from the tool-server (OOMKilled), and every stage after it behaved correctly on
    # the 3 that remained. Leaving the run un-marked keeps it out of scoring entirely.
    # A 503 here means the TOOL-SERVER went away — check its pod's lastState.terminated.reason, not this log.
    if written and errors > written * 0.10:
        raise Exception(
            f"eval matrix mostly FAILED: {errors}/{written} generations errored for run {run_id}. "
            f"Refusing to mark it results_ready — a leaderboard built on the remainder would be hollow. "
            f"See the logged errors above; if they are 503s, check the tool-server pod for OOMKilled."
        )

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE eval_runs SET status = %s WHERE id = %s", ("results_ready", run_id))

    return Output(
        {"run_id": run_id, "results": written, "errors": errors},
        metadata={
            "results": MetadataValue.int(written),
            "errors": MetadataValue.int(errors),
            "models": MetadataValue.int(len(EVAL_MODELS)),
            "questions": MetadataValue.int(len(questions)),
        },
    )
