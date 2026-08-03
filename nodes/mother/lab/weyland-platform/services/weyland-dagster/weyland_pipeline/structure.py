"""B115 Structure layer — client to the `guardrails-structure` service (the eval judge's Structure guard).

The Structure validation itself (Guardrails AI: validate `JudgeScores` + re-ask the judge to repair) runs in the
standalone **`guardrails-structure`** service, NOT here — guardrails-ai's dependency pins (`click<=8.2.0`, `rich<14`,
`coloredlogs>=15`) cannot co-install with this Dagster/dbt/huggingface image. So this module is a thin HTTP client:
POST the judge's raw output + model, get back validated scores.

**Fail-safe** — if the service is unreachable or errors, best-effort parse the raw output (the pre-B115 behaviour), so
a guard outage never sinks an eval (the same fail-open contract as Scan/Classify). Copy-portable — no Dagster imports.
"""
from __future__ import annotations

import json
import os

import httpx

_STRUCTURE_URL = os.environ.get(
    "GUARDRAILS_STRUCTURE_URL", "http://guardrails-structure.weyland.svc.cluster.local:8080"
)
_FIELDS = ("faithfulness", "answer_relevancy", "context_relevancy")


def _best_effort(text: str) -> dict:
    """Fail-safe parse (the pre-B115 behaviour): slice the outermost braces, json.loads, clamp to [0, 1]."""
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {k: max(0.0, min(1.0, float(data[k]))) for k in _FIELDS if data.get(k) is not None}


def validate_scores(raw: str, model: str, api_base: str, *, num_reasks: int = 2) -> tuple[dict, str]:
    """POST the judge's raw output to `guardrails-structure` for validate + re-ask. Returns `(scores, source)` where
    source ∈ {"guarded", "reasked", "fallback"}. Fail-safe: service unreachable / failed validation → best-effort parse."""
    try:
        r = httpx.post(
            f"{_STRUCTURE_URL}/structure/judge-scores",
            json={"raw": raw, "model": model, "api_base": api_base, "num_reasks": num_reasks},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("validation_passed") and data.get("scores"):
            return data["scores"], data.get("source", "guarded")
    except Exception:
        pass
    return _best_effort(raw), "fallback"
