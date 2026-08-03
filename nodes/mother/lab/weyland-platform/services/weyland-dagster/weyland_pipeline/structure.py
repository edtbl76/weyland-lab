"""B115 Structure layer — Guardrails AI over structured LLM output (first consumer: the eval judge).

The **Structure** path of the guardrails platform (B115): where Scan sanitizes and Classify judges safety, Structure
holds an LLM's output to a **schema** — validate it, and on a schema failure **re-ask the same model** (with the
errors) to repair. It guards producers whose output a downstream consumer parses, where a malformed blob breaks
silently.

First consumer: the RAG eval judge (`assets/eval_scores.py::_judge`). It must emit
`{faithfulness, answer_relevancy, context_relevancy}`, each a float in [0, 1]. The pre-B115 path did a raw
`json.loads` on a brace-slice — a judge that returned malformed JSON *failed the result* (lost), and one that omitted
a metric had it *silently dropped* (partial score → skewed leaderboard). This validates the contract and re-asks.

**Fail-safe** — any Guardrails import/call error → a best-effort parse (the pre-B115 behaviour), so a guard hiccup
never sinks an eval (the same fail-open contract as Scan/Classify). **Copy-portable** — no Dagster imports, so the
next structured producer (the operator's `propose_act`, extraction assets) can reuse it.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field


class JudgeScores(BaseModel):
    """The RAG judge's output contract — three metrics, each a float in [0, 1]."""

    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_relevancy: float = Field(ge=0.0, le=1.0)


_FIELDS = tuple(JudgeScores.model_fields)


def _clamp(d: dict) -> dict:
    """Keep only the schema fields, coerced to float and clamped to [0, 1]; drop missing/None (fallback path)."""
    return {k: max(0.0, min(1.0, float(d[k]))) for k in _FIELDS if d.get(k) is not None}


def _best_effort(text: str) -> dict:
    """Pre-B115 fallback: slice the outermost braces, json.loads, clamp. Silently drops missing keys."""
    return _clamp(json.loads(text[text.find("{"): text.rfind("}") + 1]))


def validate_scores(raw: str, model: str, api_base: str, *, num_reasks: int = 2) -> tuple[dict, str]:
    """Validate the judge's raw output against `JudgeScores`; on a schema failure RE-ASK the same judge model to
    repair it (Guardrails AI). Returns `(scores, source)` where source ∈ {"guarded", "reasked", "fallback"} for
    observability.

    `api_base` is the judge's OpenAI-compatible root; litellm's `ollama_chat` provider wants it WITHOUT `/v1`
    (the eval passes `.../v1`), so we strip it. Fail-safe: any Guardrails error → `_best_effort(raw)`.
    """
    base = api_base.rstrip("/")
    base = base[:-3].rstrip("/") if base.endswith("/v1") else base
    try:
        from guardrails import Guard

        guard = Guard.for_pydantic(JudgeScores)
        outcome = guard.parse(
            llm_output=raw,
            model=f"ollama_chat/{model}",
            api_base=base,
            num_reasks=num_reasks,
        )
        if outcome.validation_passed and outcome.validated_output:
            scores = _clamp(dict(outcome.validated_output))
            if len(scores) == len(_FIELDS):  # all three present + valid
                # a repair happened iff the model was re-asked (raw output changed)
                source = "reasked" if (outcome.raw_llm_output or "") != raw else "guarded"
                return scores, source
    except Exception:
        pass
    return _best_effort(raw), "fallback"
