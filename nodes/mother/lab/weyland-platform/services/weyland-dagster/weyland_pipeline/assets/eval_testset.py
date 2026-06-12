"""B4 eval — Step 2: generate an evaluation question set from the rag corpus.

Tries Ragas TestsetGenerator (Ollama generator LLM + bge embeddings); on ANY failure
falls back to a direct Ollama prompt that returns questions as JSON. Either way the
questions land in eval_questions under a new eval_run. The `notes` field records which
path produced them, so we can see whether Ragas worked on the local model.

Reuse, as designed: corpus from Postgres (rag_chunks), generator from Ollama, embeddings
from bge — no new data/model infra.
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
EVAL_GENERATOR_MODEL = os.environ.get("EVAL_GENERATOR_MODEL", "qwen3:30b-a3b")
EVAL_TEST_SIZE = int(os.environ.get("EVAL_TEST_SIZE", "10"))
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.244:11434/v1")
EVAL_METRICS = ["faithfulness", "answer_relevancy", "context_relevancy"]


def _load_corpus(postgres: PostgresResource) -> list[dict]:
    """Reconstruct each document's text from its ordered chunks."""
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.name, string_agg(c.content, E'\n\n' ORDER BY c.chunk_index)
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                GROUP BY d.id, d.name
                """
            )
            return [{"name": name, "text": text} for name, text in cur.fetchall()]


def _ragas_questions(docs: list[dict], n: int) -> list[dict]:
    """Primary path: Ragas TestsetGenerator with Ollama (OpenAI-compatible) + bge."""
    from langchain_core.documents import Document as LCDocument
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_openai import ChatOpenAI
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.testset import TestsetGenerator

    llm = LangchainLLMWrapper(
        ChatOpenAI(model=EVAL_GENERATOR_MODEL, base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=600)
    )
    emb = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5"))
    lc_docs = [LCDocument(page_content=d["text"], metadata={"name": d["name"]}) for d in docs]
    generator = TestsetGenerator(llm=llm, embedding_model=emb)
    dataset = generator.generate_with_langchain_docs(lc_docs, testset_size=n)
    out = []
    for _, row in dataset.to_pandas().iterrows():
        rc = row.get("reference_contexts")
        out.append(
            {
                "question": row.get("user_input"),
                "question_type": row.get("synthesizer_name") or "ragas",
                "reference_answer": row.get("reference"),
                "reference_contexts": json.dumps(list(rc)) if rc is not None else None,
            }
        )
    return [q for q in out if q["question"]]


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


def _direct_prompt_questions(docs: list[dict], n: int) -> list[dict]:
    """Fallback: ask Ollama directly for questions, constrained to a JSON object."""
    corpus = "\n\n".join(f"# {d['name']}\n{d['text'][:4000]}" for d in docs)[:12000]
    prompt = (
        f"Based ONLY on the following notes, write {n} diverse questions a user might ask that are "
        f"answerable from the notes. Mix simple factual questions with multi-step reasoning ones. "
        f'Respond with a JSON object of the form {{"questions": ["...", "..."]}} and nothing else.\n\n'
        f"NOTES:\n{corpus}"
    )
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
    content = resp.json()["choices"][0]["message"]["content"]
    questions = _extract_questions(content, n)
    if not questions:
        raise Exception(f"could not parse questions from generator output: {content[:200]!r}")
    return [
        {"question": q, "question_type": "direct", "reference_answer": None, "reference_contexts": None}
        for q in questions
    ]


@asset(
    group_name="eval",
    description="Generate an eval question set (Ragas; direct-prompt fallback) from the rag corpus -> eval_questions.",
)
def eval_testset(postgres: PostgresResource) -> Output[dict]:
    docs = _load_corpus(postgres)
    if not docs:
        raise Exception("No corpus in rag_chunks — run ingestion before generating an eval set.")

    method = "ragas"
    try:
        questions = _ragas_questions(docs, EVAL_TEST_SIZE)
        if not questions:
            raise Exception("Ragas returned zero questions")
    except Exception as e:
        method = f"fallback ({type(e).__name__}: {e})"
        questions = _direct_prompt_questions(docs, EVAL_TEST_SIZE)

    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO eval_runs (status, models, metrics, question_count, notes) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                ("questions_ready", EVAL_MODELS, EVAL_METRICS, len(questions), f"testset via {method}"),
            )
            run_id = cur.fetchone()[0]
            for q in questions:
                cur.execute(
                    "INSERT INTO eval_questions (run_id, question, question_type, reference_answer, reference_contexts) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (run_id, q["question"], q["question_type"], q["reference_answer"], q["reference_contexts"]),
                )

    return Output(
        {"run_id": run_id, "question_count": len(questions), "method": method},
        metadata={
            "run_id": MetadataValue.int(run_id),
            "questions": MetadataValue.int(len(questions)),
            "method": MetadataValue.text(method),
        },
    )
