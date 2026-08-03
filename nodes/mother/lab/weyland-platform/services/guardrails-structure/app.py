"""guardrails-structure — the Structure layer of the guardrails platform (B115).

Guardrails AI (output-schema validation + re-ask) runs HERE, isolated in its own image, because its dependency pins
(click<=8.2.0, coloredlogs>=15, rich<14) cannot co-install with the Dagster / dbt / huggingface monolith that produces
the structured output. Producers POST their raw LLM output + the target model; this validates it against a Pydantic
schema and, on a schema failure, RE-ASKS the same model (with the errors injected) to repair — returning the validated
object.

First consumer: the RAG eval judge (`weyland-dagster` `eval_scores._judge`), which must emit three floats in [0, 1].
Callers FAIL SAFE (a best-effort parse) when this service is unreachable, so a guard outage never sinks an eval — the
same fail-open contract as Scan (`weyland-guard`) and Classify (`llama-guard`).
"""
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# The eval judges run on Ollama (rogueone). litellm's `ollama_chat` provider wants the root WITHOUT `/v1`.
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://192.168.1.230:11434")

app = FastAPI(title="guardrails-structure")


class JudgeScores(BaseModel):
    """The RAG judge's output contract — three metrics, each a float in [0, 1]."""

    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_relevancy: float = Field(ge=0.0, le=1.0)


_FIELDS = tuple(JudgeScores.model_fields)


class JudgeScoresRequest(BaseModel):
    raw: str                       # the judge's already-generated raw output
    model: str                     # the judge model id, e.g. "mistral-small3.2:24b"
    api_base: str | None = None    # override the Ollama root; defaults to OLLAMA_BASE
    num_reasks: int = 2


class JudgeScoresResponse(BaseModel):
    scores: dict
    source: str                    # "guarded" | "reasked" | "failed[:<reason>]"
    validation_passed: bool


_guard = None  # guardrails import is heavy (litellm tree) — build once, reuse across requests


def _get_guard():
    global _guard
    if _guard is None:
        from guardrails import Guard
        _guard = Guard.for_pydantic(JudgeScores)
    return _guard


def _ollama_base(api_base: str | None) -> str:
    base = (api_base or OLLAMA_BASE).rstrip("/")
    return base[:-3].rstrip("/") if base.endswith("/v1") else base   # strip /v1 for litellm ollama_chat


@app.post("/structure/judge-scores", response_model=JudgeScoresResponse)
def judge_scores(req: JudgeScoresRequest):
    """Validate the judge's raw output against JudgeScores; RE-ASK the same judge model to repair on a schema miss.
    Returns empty scores + validation_passed=False on any failure — the caller fails safe to its own best-effort parse."""
    try:
        outcome = _get_guard().parse(
            llm_output=req.raw,
            model=f"ollama_chat/{req.model}",
            api_base=_ollama_base(req.api_base),
            num_reasks=req.num_reasks,
        )
        if outcome.validation_passed and outcome.validated_output:
            d = dict(outcome.validated_output)
            scores = {k: max(0.0, min(1.0, float(d[k]))) for k in _FIELDS if d.get(k) is not None}
            if len(scores) == len(_FIELDS):
                source = "reasked" if (outcome.raw_llm_output or "") != req.raw else "guarded"
                return JudgeScoresResponse(scores=scores, source=source, validation_passed=True)
    except Exception as exc:
        return JudgeScoresResponse(scores={}, source=f"failed:{type(exc).__name__}", validation_passed=False)
    return JudgeScoresResponse(scores={}, source="failed", validation_passed=False)


@app.get("/health")
def health():
    """Liveness — the process is up (does not import guardrails)."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — the guard (guardrails + litellm) actually imports + builds. 503 until it does, so traffic only
    arrives once the service can really validate."""
    try:
        _get_guard()
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "loading", "error": str(exc)})
