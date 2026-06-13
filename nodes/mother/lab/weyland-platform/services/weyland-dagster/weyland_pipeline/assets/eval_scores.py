"""B4 eval — Step 4: LLM-as-judge scoring of eval_results -> eval_scores.

Standalone (no asset dependency) so it can score an already-completed matrix run without
re-running the expensive run-matrix. Scores the most recent run that has results, judging only
results not yet scored (idempotent — safe to re-run, and to re-score with a different judge).

A direct Ollama call per result returns faithfulness / answer_relevancy / context_relevancy in
[0,1]. This IS what Ragas does internally — minus the dependency constellation (see
docs/b4-eval-runbook.md). Reuse-only: Ollama (judge) + Postgres.
"""
import json
import os
import re

import httpx
from dagster import Output, MetadataValue, asset

from weyland_pipeline.resources import PostgresResource

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.244:11434/v1")
# Fast, non-thinking judge (reliable JSON). Swap to mistral-small3.2:24b for more nuanced judging
# via EVAL_JUDGE_MODEL; scoring is a separate job, so re-scoring is cheap.
EVAL_JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "deepseek-coder-v2:16b")
METRICS = ("faithfulness", "answer_relevancy", "context_relevancy")


def _strip_think(text: str | None) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()


def _judge(client: httpx.Client, question: str, contexts, answer: str) -> dict:
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
    resp = client.post(
        f"{OLLAMA_BASE_URL}/chat/completions",
        json={
            "model": EVAL_JUDGE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "response_format": {"type": "json_object"},
        },
    )
    resp.raise_for_status()
    content = _strip_think(resp.json()["choices"][0]["message"].get("content") or "")
    data = json.loads(content[content.find("{"): content.rfind("}") + 1])
    out = {}
    for m in METRICS:
        if m in data and data[m] is not None:
            out[m] = max(0.0, min(1.0, float(data[m])))
    return out


@asset(
    group_name="eval",
    description="LLM-as-judge scoring of the latest run's eval_results -> eval_scores (idempotent).",
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
            # Only results that aren't already scored (idempotent re-runs).
            cur.execute(
                """
                SELECT er.id, eq.question, er.contexts, er.answer
                FROM eval_results er
                JOIN eval_questions eq ON eq.id = er.question_id
                LEFT JOIN eval_scores es ON es.result_id = er.id
                WHERE er.run_id = %s AND er.error IS NULL AND es.id IS NULL
                """,
                (run_id,),
            )
            rows = cur.fetchall()

    scored, failed = 0, 0
    with httpx.Client(timeout=600) as client:  # judge stays resident (MAX_LOADED_MODELS=1)
        for result_id, question, contexts, answer in rows:
            try:
                scores = _judge(client, question, contexts, answer)
            except Exception:
                failed += 1
                continue
            with postgres.get_connection() as conn:
                with conn.cursor() as cur:
                    for metric, score in scores.items():
                        cur.execute(
                            "INSERT INTO eval_scores (result_id, metric, score) VALUES (%s, %s, %s) "
                            "ON CONFLICT (result_id, metric) DO UPDATE SET score = EXCLUDED.score",
                            (result_id, metric, score),
                        )
            scored += 1

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE eval_runs SET status = 'scored' WHERE id = %s", (run_id,))

    return Output(
        {"run_id": run_id, "scored": scored, "failed": failed},
        metadata={
            "run_id": MetadataValue.int(run_id),
            "scored": MetadataValue.int(scored),
            "failed": MetadataValue.int(failed),
            "judge": MetadataValue.text(EVAL_JUDGE_MODEL),
        },
    )
