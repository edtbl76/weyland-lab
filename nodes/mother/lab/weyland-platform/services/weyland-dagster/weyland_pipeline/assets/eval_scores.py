"""B4 eval — Step 5: judge-PANEL scoring of eval_results -> eval_scores.

Each result is scored by EVERY judge in the panel (>=3), and the eval_leaderboard view averages
across judges — which collapses the per-judge ranking swing we observed (single-judge LLM-as-judge
is noisy; qwen3:30b-a3b went 5th->1st just by swapping the judge — see docs/b4-eval-runbook.md).

Standalone + idempotent per (result, judge): re-runs only score pairs not yet done, so adding a
judge or resuming after a crash is cheap. Judges are non-thinking models (reliable JSON under
json_object). Reuse-only: Ollama (judges) + Postgres.
"""
import os
import re
from contextlib import contextmanager

import httpx
from dagster import Output, MetadataValue, asset, get_dagster_logger

from weyland_pipeline.resources import PostgresResource
from weyland_pipeline.structure import validate_scores

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
# Panel of non-thinking judges (reliable JSON); the eval_leaderboard view averages across them.
JUDGES = [
    j.strip()
    for j in os.environ.get(
        "EVAL_JUDGES", "mistral-small3.2:24b,deepseek-coder-v2:16b,qwen3-coder:30b"
    ).split(",")
    if j.strip()
]
METRICS = ("faithfulness", "answer_relevancy", "context_relevancy")

# B84 P2a — fail-safe MLflow tracing for the judge panel: each judge verdict → a span in the `eval` experiment
# (~360/run: models × questions × judges). No-op if MLflow is unset/unreachable — tracing must never fail an eval.
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "")
_traced = [False]


@contextmanager
def _judge_span(judge_model: str, question: str):
    if not MLFLOW_TRACKING_URI:
        yield None
        return
    try:
        import mlflow
        if not _traced[0]:
            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment("eval")
            _traced[0] = True
        with mlflow.start_span(name="judge", span_type="LLM") as span:
            if span is not None:
                span.set_inputs({"judge": judge_model, "question": question[:200]})
            yield span
    except Exception:
        yield None


def _strip_think(text: str | None) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def _judge(client: httpx.Client, judge_model: str, question: str, contexts, answer: str) -> dict:
    ctx = "\n\n".join(
        (c.get("content", "") if isinstance(c, dict) else str(c)) for c in (contexts or [])
    )[:8000]
    prompt = (
        "You are a strict RAG evaluator. Score the ANSWER on three metrics, each a float 0.0-1.0:\n"
        "- faithfulness: is the ANSWER supported by the CONTEXT (no invented facts)?\n"
        "- answer_relevancy: does the ANSWER address the QUESTION?\n"
        "- context_relevancy: is the CONTEXT relevant to the QUESTION?\n"
        'Respond ONLY with JSON: {"faithfulness":0.0,"answer_relevancy":0.0,"context_relevancy":0.0}\n\n'
        f"QUESTION:\n{question}\n\nCONTEXT:\n{ctx}\n\nANSWER:\n{_strip_think(answer)}"
    )
    with _judge_span(judge_model, question) as span:
        resp = client.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json={
                "model": judge_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        content = _strip_think(resp.json()["choices"][0]["message"].get("content") or "")
        # B115 Structure layer — validate the judge's JSON against JudgeScores and RE-ASK the judge to repair on a
        # schema miss (Guardrails AI); fail-safe to a best-effort parse so a guard hiccup never sinks the eval.
        scores, structure_source = validate_scores(content, judge_model, OLLAMA_BASE_URL)
        if span is not None:
            span.set_outputs({**scores, "_structure": structure_source})
        return scores


@asset(
    group_name="eval",
    description="Judge-panel LLM-as-judge scoring of the latest run's eval_results -> eval_scores.",
)
def eval_scores(postgres: PostgresResource) -> Output[dict]:
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM eval_runs WHERE status IN ('results_ready','scored') ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                raise Exception("no run with results to score — run the matrix first")
            run_id = row[0]

    scored, failed, errors_logged = 0, 0, 0
    log = get_dagster_logger()
    # Judge-outer: each judge model loads once (MAX_LOADED_MODELS=1) and scores all results
    # it hasn't scored yet, before the next judge swaps in.
    for judge_model in JUDGES:
        with postgres.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT er.id, eq.question, er.contexts, er.answer
                    FROM eval_results er
                    JOIN eval_questions eq ON eq.id = er.question_id
                    WHERE er.run_id = %s AND er.error IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM eval_scores es WHERE es.result_id = er.id AND es.judge = %s
                      )
                    """,
                    (run_id, judge_model),
                )
                rows = cur.fetchall()
        log.info(f"judge {judge_model}: {len(rows)} results to score "
                 f"(already-scored pairs are skipped — scoring is idempotent per result+judge)")
        j_t0, j_scored = __import__("time").monotonic(), scored
        with httpx.Client(timeout=600) as client:
            for result_id, question, contexts, answer in rows:
                try:
                    scores = _judge(client, judge_model, question, contexts, answer)
                except Exception as exc:
                    # B96 — LOG the error. This except used to swallow it entirely, so a run where 351 of 360
                    # judge calls failed still reported SUCCESS in 85s and wrote a hollow leaderboard
                    # (2026-07-21, run 8). Log the first few per judge — enough to diagnose, not enough to
                    # flood a run with 120 identical tracebacks.
                    if errors_logged < 5:
                        log.warning(f"judge {judge_model} failed on result {result_id}: "
                                    f"{type(exc).__name__}: {str(exc)[:300]}")
                        errors_logged += 1
                    failed += 1
                    continue
                with postgres.get_connection() as conn:
                    with conn.cursor() as cur:
                        for metric, score in scores.items():
                            cur.execute(
                                "INSERT INTO eval_scores (result_id, metric, judge, score) VALUES (%s, %s, %s, %s) "
                                "ON CONFLICT (result_id, metric, judge) DO UPDATE SET score = EXCLUDED.score",
                                (result_id, metric, judge_model, score),
                            )
                scored += 1
                if scored % 10 == 0:
                    log.info(f"  scored {scored} pairs so far | {failed} failed")

        log.info(f"judge {judge_model} done in {int(__import__('time').monotonic() - j_t0)}s "
                 f"| +{scored - j_scored} scored")

    log.info(f"eval scoring run {run_id} COMPLETE: {scored} pairs scored, {failed} failed")

    # B96 — FAIL LOUDLY on a hollow run. Scoring is best-effort per (result, judge) so a couple of flaky judge
    # calls shouldn't sink the run — but a mostly-failed pass must NOT be reported as success: it silently
    # publishes a leaderboard computed from a handful of scores, which is worse than no leaderboard at all.
    # The run is left un-marked ('results_ready'), so re-running resumes and fills the gaps (idempotent per pair).
    attempted = scored + failed
    if attempted and failed > attempted * 0.10:
        raise Exception(
            f"eval scoring mostly FAILED: {failed}/{attempted} judge calls errored "
            f"({scored} scored). Leaderboard for run {run_id} would be hollow — refusing to mark it scored. "
            f"See the logged judge errors above; re-run to resume (scoring is idempotent per result+judge)."
        )

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE eval_runs SET status = 'scored' WHERE id = %s", (run_id,))

    return Output(
        {"run_id": run_id, "scored": scored, "failed": failed, "judges": JUDGES},
        metadata={
            "run_id": MetadataValue.int(run_id),
            "scored_pairs": MetadataValue.int(scored),
            "failed": MetadataValue.int(failed),
            "judges": MetadataValue.text(", ".join(JUDGES)),
        },
    )
