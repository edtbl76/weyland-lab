"""B103 eval — codify the Langfuse ONLINE evaluator set (native LLM-as-judge) so a Langfuse DB reset recreates it.

Langfuse's eval engine IS programmatic — via `/api/public/unstable/{evaluators,evaluation-rules}` (NOT `/eval-configs`,
which 404s; the earlier probe checked the wrong path). This reconciles, idempotently:
  - 2 **custom** evaluators (`citation`, `refusal`) — weyland-specific criteria absent from Langfuse's managed library.
  - 9 evaluation **rules** binding evaluators (7 managed + the 2 custom) to `rag-generate` observations. Native rules
    have **no per-rule model** — all share the LLM connection's default (set to `wl-judge-oss` → $0). "All native on
    wl-judge-oss" was the chosen tier; per-criterion Haiku would need the old batch judge, which this REPLACES.

Skips any evaluator/rule whose name already exists. Env: LANGFUSE_HOST + LANGFUSE_PUBLIC_KEY/SECRET_KEY.
Run: `kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/langfuse_evaluators.py`
(or the `langfuse_codified_evals` registrations asset). Fixtures/model live elsewhere: git `eval_sets/` (SSOT) + the
Langfuse LLM connection.
"""
import os

import httpx

LF = os.environ["LANGFUSE_HOST"].rstrip("/")
AUTH = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
EV, RULE = "/api/public/unstable/evaluators", "/api/public/unstable/evaluation-rules"
FILTER = [{"column": "name", "operator": "any of", "value": ["rag-generate"], "type": "stringOptions"}]
_OUT = {"dataType": "NUMERIC", "score": {"description": "Score between 0 and 1"},
        "reasoning": {"description": "One sentence reasoning"}}

# weyland-specific evaluators (not in the managed library)
CUSTOM_EVALUATORS = [
    {"type": "llm_as_judge", "name": "citation", "variables": ["query", "generation"], "outputDefinition": _OUT,
     "prompt": "Does the ANSWER cite the source name(s) it used, as the assistant is required to? Score 1 if it cites "
               "at least one source or document name, 0 if it makes claims with no citation. Query: {{query}} "
               "Answer: {{generation}}"},
    {"type": "llm_as_judge", "name": "refusal", "variables": ["query", "context", "generation"], "outputDefinition": _OUT,
     "prompt": "If the context does not contain the answer, the ANSWER must say so plainly rather than guess. Score 1 "
               "if it answers from the context OR correctly states the info is unavailable, 0 if it fabricates or "
               "guesses. Query: {{query}} Context: {{context}} Answer: {{generation}}"},
]

_QG = [{"variable": "query", "source": "input"}, {"variable": "generation", "source": "output"}]
_CTX = [{"variable": "query", "source": "input"}, {"variable": "context", "source": "input"}]
_FAI = [{"variable": "context", "source": "input"}, {"variable": "answer", "source": "output"}]
_REF = _CTX + [{"variable": "generation", "source": "output"}]

# (rule name, evaluator name, evaluator scope, variable mapping). Mapping must cover the evaluator's variables exactly once;
# the RAG context+question are concatenated in the observation Input, so `context` maps to Input alongside `query`.
RULES = [
    ("Relevance", "Relevance", "managed", _QG), ("Helpfulness", "Helpfulness", "managed", _QG),
    ("Hallucination", "Hallucination", "managed", _QG), ("Conciseness", "Conciseness", "managed", _QG),
    ("Toxicity", "Toxicity", "managed", _QG), ("Contextrelevance", "Contextrelevance", "managed", _CTX),
    ("Faithfulness", "Faithfulness", "managed", _FAI),
    ("citation", "citation", "project", _QG), ("refusal", "refusal", "project", _REF),
]


def main():
    with httpx.Client(base_url=LF, auth=AUTH, timeout=120) as c:
        have = {e["name"] for e in c.get(EV, params={"limit": 100}, timeout=30).json().get("data", [])}
        for spec in CUSTOM_EVALUATORS:
            if spec["name"] in have:
                print("evaluator exists:", spec["name"]); continue
            print("evaluator", spec["name"], c.post(EV, json=spec, timeout=60).status_code)
        have = {r["name"] for r in c.get(RULE, params={"limit": 100}, timeout=30).json().get("data", [])}
        for name, ev, scope, mapping in RULES:
            if name in have:
                print("rule exists:", name); continue
            body = {"name": name, "evaluator": {"name": ev, "scope": scope, "type": "llm_as_judge"},
                    "target": "observation", "enabled": True, "sampling": 1, "filter": FILTER, "mapping": mapping}
            try:
                print("rule", name, c.post(RULE, json=body, timeout=120).status_code)
            except Exception as e:   # rule create can be slow (cold judge model) — don't let one stall the rest
                print("rule", name, "ERR", type(e).__name__)
    print(f"langfuse online evaluators reconciled: {len(RULES)} rules + {len(CUSTOM_EVALUATORS)} custom evaluators")


if __name__ == "__main__":
    main()
