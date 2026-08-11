"""B4 eval — Step 2: generate an evaluation question set from the rag corpus.

Direct-prompt generation via Ollama. **Ragas was REJECTED** — broken in the current release
(hard-imports a deleted langchain path) + ~100-package Google-Cloud-SDK bloat; full decision
record in docs/b4-eval-runbook.md. Corpus from Postgres (rag_chunks) -> qwen3:30b-a3b writes
questions answerable from it -> eval_questions. Reuse-only: no new data/model infra.
"""
import json
import os
import re

import httpx
from dagster import Output, MetadataValue, asset

from weyland_pipeline.resources import PostgresResource

EVAL_MODELS = os.environ.get(
    "EVAL_MODELS",
    "qwen3:30b-a3b,qwen3-coder:30b,deepseek-coder-v2:16b,gpt-oss:20b,qwen3:14b,mistral-small3.2:24b",
).split(",")
# Non-thinking generator: thinking models (qwen3) intermittently return empty content under the
# json_object constraint (the <think> block eats the generation). mistral is reliable for JSON.
EVAL_GENERATOR_MODEL = os.environ.get("EVAL_GENERATOR_MODEL", "mistral-small3.2:24b")
EVAL_TEST_SIZE = int(os.environ.get("EVAL_TEST_SIZE", "10"))
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.230:11434/v1")
EVAL_METRICS = ["faithfulness", "answer_relevancy", "context_relevancy"]

# B96 — GOLDEN question set. Generating fresh questions every run made the leaderboard non-comparable ACROSS
# runs: each run was graded on a different exam, so a score delta measured question difficulty, not system
# quality. That confounded a real investigation (2026-07-20): run 5 scored ~0.30 below runs 3/4 across ALL SIX
# models at once, which reads exactly like a system-wide regression and was not one.
#
#   golden    (default) — fixed questions from golden_questions.json. Cross-run comparable: a score change now
#                         means the SYSTEM changed. Required to measure retrieval work (B74) before/after.
#   generated           — the original per-run LLM generation. Keep it: a static exam can be overfit to, and
#                         regenerating occasionally checks that the golden set isn't unrepresentative.
#
# The file lives INSIDE weyland_pipeline/ so the existing `COPY weyland_pipeline/` in the Dockerfile picks it
# up — no image-build change needed to add or edit questions.
EVAL_QUESTION_SOURCE = os.environ.get("EVAL_QUESTION_SOURCE", "golden")
GOLDEN_QUESTIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval_sets", "golden.json")  # B103 — moved into the eval_sets/ SSOT catalog (was golden_questions.json)


def _load_golden_questions() -> list[dict]:
    """Read the pinned question set. Fails LOUDLY rather than silently falling back to generation — a silent
    fallback would produce a run that LOOKS golden but isn't comparable, which is the exact bug B96 fixes.

    Deliberately ignores EVAL_TEST_SIZE: in golden mode the FILE is the definition of the exam. Truncating it
    to N would silently change the exam between runs and reintroduce the incomparability.

    Each entry carries a `type` (`conceptual` | `lexical`) stored as `question_type`, so the leaderboard can be
    sliced by half — the whole point of the mixed set (see the file's own _comment)."""
    with open(GOLDEN_QUESTIONS_PATH) as fh:
        data = json.load(fh)
    out = []
    for q in data.get("questions", []):
        if isinstance(q, str):          # tolerate a plain-string list
            text, qtype = q.strip(), "golden"
        else:
            text, qtype = str(q.get("q", "")).strip(), f"golden-{q.get('type', 'unknown')}"
        if text:
            out.append({"question": text, "question_type": qtype,
                        "reference_answer": None, "reference_contexts": None})
    if not out:
        raise Exception(f"golden set {GOLDEN_QUESTIONS_PATH} has no questions")
    return out


def _load_corpus(postgres: PostgresResource) -> list[dict]:
    """Reconstruct each document's text from its ordered chunks."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.name, string_agg(c.content, E'\n\n' ORDER BY c.chunk_index)
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE d.source_type = 'markdown'   -- evals are over knowledge/docs, not ingested code (B25b)
                GROUP BY d.id, d.name
                """
            )
            return [{"name": name, "text": text} for name, text in cur.fetchall()]


def _extract_questions(content: str, n: int) -> list[str]:
    """Pull a question list out of a possibly-messy LLM reply: strip qwen3 <think> blocks,
    try JSON object/array, then fall back to line parsing."""
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    candidates = [
        content,
        content[content.find("{"): content.rfind("}") + 1],
        content[content.find("["): content.rfind("]") + 1],
    ]
    for cand in candidates:
        if not cand.strip():
            continue
        try:
            data = json.loads(cand)
        except Exception:
            continue
        if isinstance(data, dict):  # expected: {"questions": [...]}
            data = data.get("questions") or next((v for v in data.values() if isinstance(v, list)), [])
        if isinstance(data, list):
            qs = [str(q).strip() for q in data if str(q).strip()]
            if qs:
                return qs[:n]
    # Last resort: any line that ends in a question mark (strip list markers/numbering).
    lines = [re.sub(r"^[\s\-\*\d\.\)]+", "", ln).strip() for ln in content.splitlines()]
    return [ln for ln in lines if ln.endswith("?")][:n]


def _generate_questions(docs: list[dict], n: int) -> list[dict]:
    """Ask Ollama for questions answerable from the corpus, constrained to a JSON object."""
    corpus = "\n\n".join(f"# {d['name']}\n{d['text'][:4000]}" for d in docs)[:12000]
    prompt = (
        f"Based ONLY on the following notes, write {n} diverse questions a user might ask that are "
        f"answerable from the notes. Mix simple factual questions with multi-step reasoning ones. "
        f'Respond with a JSON object of the form {{"questions": ["...", "..."]}} and nothing else.\n\n'
        f"NOTES:\n{corpus}"
    )
    last = ""
    for _ in range(2):  # retry once — generators occasionally return empty content
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json={
                "model": EVAL_GENERATOR_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "response_format": {"type": "json_object"},  # constrain output to valid JSON
            },
            timeout=600,
        )
        resp.raise_for_status()
        last = resp.json()["choices"][0]["message"].get("content") or ""
        questions = _extract_questions(last, n)
        if questions:
            return [
                {"question": q, "question_type": "direct", "reference_answer": None, "reference_contexts": None}
                for q in questions
            ]
    raise Exception(f"could not parse questions from generator output: {last[:200]!r}")


@asset(
    group_name="eval",
    description="Load the GOLDEN eval question set (or generate one via Ollama) -> eval_questions.",
)
def eval_testset(postgres: PostgresResource) -> Output[dict]:
    # The corpus check runs in BOTH modes: golden questions are still answered against the live corpus, so an
    # empty corpus makes the run meaningless either way — fail here rather than produce a floor-score leaderboard.
    docs = _load_corpus(postgres)
    if not docs:
        raise Exception("No corpus in rag_chunks — run ingestion before generating an eval set.")

    if EVAL_QUESTION_SOURCE == "golden":
        questions = _load_golden_questions()
        notes = f"golden question set ({len(questions)}q) — cross-run comparable"
    else:
        questions = _generate_questions(docs, EVAL_TEST_SIZE)
        notes = "questions via direct-prompt (GENERATED — NOT comparable to golden runs)"

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO eval_runs (status, models, metrics, question_count, notes) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ("questions_ready", EVAL_MODELS, EVAL_METRICS, len(questions), notes),
            )
            run_id = cur.fetchone()[0]
            for q in questions:
                cur.execute(
                    "INSERT INTO eval_questions (run_id, question, question_type, reference_answer, reference_contexts) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (run_id, q["question"], q["question_type"], q["reference_answer"], q["reference_contexts"]),
                )

    return Output(
        {"run_id": run_id, "question_count": len(questions)},
        metadata={
            "run_id": MetadataValue.int(run_id),
            "questions": MetadataValue.int(len(questions)),
        },
    )
