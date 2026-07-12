"""B4 eval — Step 5: judge-PANEL scoring of eval_results -> eval_scores.

Each result is scored by EVERY judge in the panel (>=3), and the eval_leaderboard view averages
across judges — which collapses the per-judge ranking swing we observed (single-judge LLM-as-judge
is noisy; qwen3:30b-a3b went 5th->1st just by swapping the judge — see docs/b4-eval-runbook.md).

Standalone + idempotent per (result, judge): re-runs only score pairs not yet done, so adding a
judge or resuming after a crash is cheap. Judges are non-thinking models (reliable JSON under
json_object). Reuse-only: Ollama (judges) + Postgres.
"""
import json
import os
import re

import httpx
from dagster import Output, MetadataValue, asset

from weyland_pipeline.resources import PostgresResource

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
    data = json.loads(content[content.find("{"): content.rfind("}") + 1])
    return {m: max(0.0, min(1.0, float(data[m]))) for m in METRICS if m in data and data[m] is not None}


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

    scored, failed = 0, 0
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
        with httpx.Client(timeout=600) as client:
            for result_id, question, contexts, answer in rows:
                try:
                    scores = _judge(client, judge_model, question, contexts, answer)
                except Exception:
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
