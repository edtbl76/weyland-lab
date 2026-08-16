"""B4 eval — Step 3 (graph-backed): each MODEL is its own retryable Dagster step.

Fans out over EVAL_MODELS via DynamicOut; each branch (`run_one_model`) drains the
shared 16 GB GPU, then runs every question for that model through the tool-server
`/context/ask` (retrieve + generate), storing answer + contexts in eval_results.
`finalize_matrix` aggregates and enforces the hollow-run gate (B96).

The eval JOB runs on the in_process executor (see schedules.py), so the mapped model
steps execute SERIALLY — the GPU holds one model at a time (OLLAMA_MAX_LOADED_MODELS=1),
and drain_gpu guarantees a clean card before each load instead of racing an eviction
(the old 503 swap thrash). Per-model steps are individually visible + retryable in the UI.

Reuse-only: tool-server (RAG), Ollama (generation), Postgres (storage). No new infra.
"""
import json
import os
import time

import httpx
from dagster import (
    DynamicOut,
    DynamicOutput,
    MetadataValue,
    Output,
    get_dagster_logger,
    graph_asset,
    op,
)

from weyland_pipeline.assets.eval_testset import EVAL_MODELS
from weyland_pipeline.gpu import drain_gpu
from weyland_pipeline.resources import PostgresResource

TOOL_SERVER_URL = os.environ.get("TOOL_SERVER_URL", "http://weyland-tool-server:8080")
EVAL_BACKEND = os.environ.get("EVAL_BACKEND", "pgvector")
EVAL_ASK_LIMIT = int(os.environ.get("EVAL_ASK_LIMIT", "3"))
# rogueone Ollama (native API root, no /v1) — for draining models between eval models.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.230:11434")

# Hollow-run gate (B96): individual generations may fail (a flaky call shouldn't sink the
# matrix), but a mostly-failed run must NOT be marked results_ready — downstream scoring
# filters on `error IS NULL` and would publish a leaderboard built from the few survivors.
_HOLLOW_THRESHOLD = 0.10


def _mapping_key(model: str) -> str:
    # Dynamic-output mapping keys must be alphanumeric/underscore; model names aren't (qwen3:14b).
    return "".join(c if c.isalnum() else "_" for c in model)


@op(out=DynamicOut(), description="Fan out one branch per eval model (each loads once, run serially).")
def fan_out_models(eval_testset: dict):
    run_id = eval_testset["run_id"]
    for model in EVAL_MODELS:
        yield DynamicOutput({"run_id": run_id, "model": model}, mapping_key=_mapping_key(model))


@op(description="Drain the GPU, then run every question for one model through /context/ask -> eval_results.")
def run_one_model(spec: dict, postgres: PostgresResource) -> dict:
    log = get_dagster_logger()
    run_id, model = spec["run_id"], spec["model"]

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, question FROM eval_questions WHERE run_id = %s ORDER BY id", (run_id,))
            questions = cur.fetchall()  # [(question_id, question_text), ...]

    # Clean the shared card before this model loads: unload whatever's resident and wait until the
    # GPU is empty, so `model` loads clean instead of racing an eviction mid-request (503 thrash).
    drained = drain_gpu(OLLAMA_BASE_URL, log=log)
    if not drained["clear"]:
        log.warning(f"[{model}] GPU did not clear (still resident: {drained['held']}) — proceeding, expect contention")
    log.info(f"[{model}] starting {len(questions)} questions (loads on first /context/ask — expect a pause)")

    written, errors = 0, 0
    m_t0 = time.monotonic()
    with httpx.Client(timeout=600) as client:
        for question_id, question in questions:
            t0 = time.monotonic()
            answer, contexts, error = None, None, None
            # Retry transient model-load contention: a swap/load 503s (or the tool-server 502s
            # "LLM call failed") for a few seconds while Ollama loads. 1 try + 3 backed-off retries.
            for attempt in range(4):
                try:
                    resp = client.post(
                        f"{TOOL_SERVER_URL}/context/ask",
                        json={"query": question, "backend": EVAL_BACKEND, "limit": EVAL_ASK_LIMIT, "model": model},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    answer, contexts, error = data.get("answer"), data.get("sources"), None
                    break
                except Exception as e:
                    error = f"{type(e).__name__}: {str(e)[:200]}"
                    transient = isinstance(e, (httpx.ConnectError, httpx.ReadTimeout)) or (
                        isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (502, 503)
                    )
                    if transient and attempt < 3:
                        time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s — lets the model finish loading
                        continue
                    if errors <= 5:
                        log.warning(f"/context/ask failed (model={model}, q={question_id}) after {attempt + 1} tries: {error}")
                    errors += 1
                    break
            latency_ms = int((time.monotonic() - t0) * 1000)

            # Fresh connection per write so a long run never holds one open across HTTP,
            # and partial progress persists if the step dies mid-model.
            with postgres.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO eval_results "
                        "(run_id, question_id, model, backend, answer, contexts, latency_ms, error) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            run_id, question_id, model, EVAL_BACKEND, answer,
                            json.dumps(contexts) if contexts is not None else None, latency_ms, error,
                        ),
                    )
            written += 1

    log.info(f"[{model}] done in {int(time.monotonic() - m_t0)}s | {written} cells, {errors} errors")
    return {"run_id": run_id, "model": model, "written": written, "errors": errors}


@op(description="Aggregate per-model results, enforce the hollow-run gate, mark the run results_ready.")
def finalize_matrix(per_model: list, postgres: PostgresResource) -> Output[dict]:
    log = get_dagster_logger()
    per_model = [r for r in per_model if r]
    if not per_model:
        raise Exception("eval matrix produced no model results")
    run_id = per_model[0]["run_id"]
    written = sum(r["written"] for r in per_model)
    errors = sum(r["errors"] for r in per_model)
    log.info(f"eval matrix run {run_id} COMPLETE: {written} cells written, {errors} errors "
             f"({(errors / written * 100) if written else 0:.1f}%)")

    # B96 — FAIL LOUDLY on a hollow matrix so a leaderboard isn't built from a handful of survivors.
    if written and errors > written * _HOLLOW_THRESHOLD:
        raise Exception(
            f"eval matrix mostly FAILED: {errors}/{written} generations errored for run {run_id}. "
            f"Refusing to mark it results_ready — a leaderboard on the remainder would be hollow. "
            f"See the logged per-model errors; if they are 503s, check the GPU / tool-server."
        )

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE eval_runs SET status = %s WHERE id = %s", ("results_ready", run_id))

    return Output(
        {"run_id": run_id, "results": written, "errors": errors},
        metadata={
            "results": MetadataValue.int(written),
            "errors": MetadataValue.int(errors),
            "models": MetadataValue.int(len(per_model)),
        },
    )


@graph_asset(
    name="eval_run_matrix",
    group_name="eval",
    description="Per-model eval matrix (each model a retryable step): /context/ask -> eval_results.",
)
def eval_run_matrix(eval_testset):
    specs = fan_out_models(eval_testset)
    results = specs.map(run_one_model)
    return finalize_matrix(results.collect())
