#!/usr/bin/env python3
"""Register the lab's prompts to the MLflow Prompt Registry (B100 Phase 2).

The registry is the source of truth for the LIVE prompt version each service fetches at runtime (TTL-cached, via
`prompts.load_prompt`); each service also bakes a matching copy of the text as its fail-safe fallback. Idempotent:
registers a new version only when the template text changed, then moves the `production` alias to it — so editing a
prompt here + re-running this script hot-swaps it across the services within their cache TTL, no redeploy.

Run inside a pod that already has full `mlflow` (rogueone's shell python may not) — pipe this script to its stdin;
the pod supplies both mlflow and the in-cluster MLFLOW_TRACKING_URI:
  kubectl -n weyland exec -i deploy/weyland-agent -- python < scripts/register_prompts.py
Or standalone from any host with mlflow>=3.0 installed:
  MLFLOW_TRACKING_URI=http://192.168.1.243:30500 python scripts/register_prompts.py
"""
import os

import mlflow

# The Prompt Registry API moved to the `mlflow.genai` namespace in 3.x; prefer it, fall back to the (deprecated)
# top-level for older builds.
try:
    from mlflow.genai import load_prompt, register_prompt, set_prompt_alias
except Exception:
    from mlflow import load_prompt, register_prompt, set_prompt_alias

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000"))
ALIAS = os.getenv("PROMPT_ALIAS", "production")

# name -> template. The canonical text; each service keeps a matching baked fallback constant. The agent/operator/eval
# prompts join here as they're wired (Phase 2 fan-out).
PROMPTS = {
    # Shared by the tool-server /context/ask AND the weyland-agent generate step (identical text).
    "rag_system": (
        "You are the Weyland lab assistant. Answer the question using ONLY the context "
        "chunks provided. If the context does not contain the answer, say so plainly rather "
        "than guessing. Cite the source name(s) you used."
    ),
    # weyland-operator system prompt (static).
    "operator_system": (
        "You are the weyland homelab operator. Answer questions by calling the read tools (status, context_search, "
        "context_ask), grounded in their results — never invent lab state, and say so plainly if the knowledge base has "
        "nothing. To CHANGE lab state (trigger a pipeline, run/score evals) you cannot act directly — call propose_act "
        "and the user will be asked to confirm; never claim an action ran. Keep replies short (this goes to Telegram)."
    ),
    # weyland-agent grade prompt — templated ({question}/{context} filled via str.format at the call site).
    "agent_grade": (
        "Question: {question}\n\nRetrieved context:\n{context}\n\nDoes the context contain enough information to "
        "answer the question? Reply with exactly YES or NO on the first line, then one sentence of reason."
    ),
    # weyland-agent reflect prompt — templated ({backend}/{question}/{others}).
    "agent_reflect": (
        "The search for the question below returned weak results from the '{backend}' vector backend.\n"
        "Question: {question}\n"
        "Rewrite the search query to retrieve better chunks, and pick the backend most likely to help "
        "(current: {backend}; others: {others}).\n"
        "Respond EXACTLY as two lines:\nQUERY: <rewritten query>\nBACKEND: <one backend name>"
    ),
}


def _sync(name: str, template: str) -> None:
    try:
        cur = load_prompt(f"prompts:/{name}@{ALIAS}")
        if cur.template == template:
            print(f"{name}: unchanged (v{cur.version})")
            return
    except Exception:
        pass  # not registered yet, or no production alias — fall through to register
    pv = register_prompt(name=name, template=template, commit_message="sync from register_prompts.py")
    set_prompt_alias(name=name, alias=ALIAS, version=pv.version)
    print(f"{name}: registered v{pv.version} -> @{ALIAS}")


if __name__ == "__main__":
    for _name, _template in PROMPTS.items():
        _sync(_name, _template)
