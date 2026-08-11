"""B103 eval — the CODIFIED LLM-as-judge. Langfuse's eval-config API is UI/internal-only in v3.225.1 (POST
/api/public/eval-configs → 404), so instead of a handful of hand-clicked UI evaluators we run an EXHAUSTIVE catalog
of judge criteria in code and POST the results to the Langfuse **Scores** API (200). Same rendering on the trace as a
native evaluator, but unlimited criteria, fully GitOps, and durable across a Langfuse DB reset.

Reads recent `rag-generate` generations from Langfuse, scores each criterion via **LiteLLM** (tiered per the design:
`wl-judge-oss` = gpt-oss:20b, $0, for the cheap criteria; `claude-haiku` for the harder discriminating one), and posts a
0–1 NUMERIC score + one-line reason. Idempotent: deterministic score ids (obs+criterion) → re-runs upsert, no dupes.

Env (user-code pod): LANGFUSE_HOST + LANGFUSE_PUBLIC_KEY/SECRET_KEY, LITELLM_BASE_URL + LITELLM_API_KEY.
Run: `kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/langfuse_evaluators.py`
(or materialize the `langfuse_codified_evals` asset). Tunables: EVAL_LOOKBACK_HOURS (24), EVAL_MAX_OBS (50).
"""
import datetime
import hashlib
import json
import os
import re

import httpx

LF = os.environ["LANGFUSE_HOST"].rstrip("/")
LF_AUTH = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
LITE = os.environ.get("LITELLM_BASE_URL", "http://litellm.weyland.svc.cluster.local:4000/v1").rstrip("/")
LITE_KEY = os.environ["LITELLM_API_KEY"]
LOOKBACK = int(os.getenv("EVAL_LOOKBACK_HOURS", "24"))
MAX_OBS = int(os.getenv("EVAL_MAX_OBS", "50"))

OSS, HAIKU = "wl-judge-oss", "claude-haiku"
# criterion -> (judge model, needs_context, instruction)
CATALOG = {
    "relevance":    (OSS,   False, "Does the ANSWER directly address the QUESTION and stay on topic?"),
    "helpfulness":  (OSS,   False, "Is the ANSWER helpful and complete for the QUESTION?"),
    "conciseness":  (OSS,   False, "Is the ANSWER concise — free of padding, hedging, and repetition?"),
    "citation":     (OSS,   False, "Does the ANSWER cite the source name(s) it used, as the system prompt requires?"),
    "groundedness": (HAIKU, True,  "Is EVERY factual claim in the ANSWER supported by the CONTEXT? (hallucination = low)"),
    "refusal":      (OSS,   True,  "If the CONTEXT does not contain the answer, does the ANSWER say so plainly instead "
                                   "of guessing? Score 1 if it either answered FROM the context OR correctly declined."),
}

_JUDGE = (
    "You are a strict, fair evaluator. Criterion: {criterion}\n\n"
    "QUESTION:\n{question}\n\n{context_block}ANSWER:\n{answer}\n\n"
    'Reply with ONLY a JSON object: {{"score": <float 0.0-1.0>, "reason": "<one short sentence>"}}. '
    "1.0 = fully satisfies the criterion; 0.0 = fails it."
)


def _parse_input(inp):
    """`rag-generate` input is a chat messages list; the user turn is 'Context:\\n<chunks>\\n\\nQuestion: <q>'. Return
    (question, context); defensive — fall back to the raw text if the shape differs."""
    try:
        msgs = inp if isinstance(inp, list) else json.loads(inp)
        user = next(m["content"] for m in reversed(msgs) if isinstance(m, dict) and m.get("role") == "user")
    except Exception:
        user = inp if isinstance(inp, str) else json.dumps(inp)
    if "\n\nQuestion:" in user:
        ctx, q = user.rsplit("\n\nQuestion:", 1)
        return q.strip(), ctx.strip()
    return user.strip(), user.strip()


def _judge(c, model, criterion, question, context, answer, needs_ctx):
    prompt = _JUDGE.format(criterion=criterion, question=question, answer=answer,
                           context_block=(f"CONTEXT:\n{context}\n\n" if needs_ctx else ""))
    r = c.post(f"{LITE}/chat/completions", headers={"Authorization": f"Bearer {LITE_KEY}"}, timeout=120,
               json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    txt = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    obj = json.loads(m.group(0)) if m else {}
    return (float(obj["score"]), str(obj.get("reason", ""))[:500]) if "score" in obj else (None, txt[:200])


def ensure_score_configs(c):
    """Define each score's schema (0–1 numeric) so the UI + annotation render them consistently. Ignore 'already exists'."""
    for name in CATALOG:
        try:
            c.post(f"{LF}/api/public/score-configs", auth=LF_AUTH,
                   json={"name": name, "dataType": "NUMERIC", "minValue": 0, "maxValue": 1})
        except Exception:
            pass


def main():
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=LOOKBACK)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with httpx.Client() as c:
        ensure_score_configs(c)
        obs = c.get(f"{LF}/api/public/observations", auth=LF_AUTH, timeout=30,
                    params={"name": "rag-generate", "type": "GENERATION", "fromStartTime": since, "limit": MAX_OBS}
                    ).json().get("data", [])
        posted = 0
        for o in obs:
            answer = o.get("output")
            if not answer:
                continue
            answer = answer if isinstance(answer, str) else json.dumps(answer)
            question, context = _parse_input(o.get("input"))
            for name, (model, needs_ctx, criterion) in CATALOG.items():
                try:
                    score, reason = _judge(c, model, criterion, question, context, answer, needs_ctx)
                    if score is None:
                        continue
                    c.post(f"{LF}/api/public/scores", auth=LF_AUTH, timeout=30, json={
                        "id": "eval-" + hashlib.sha1(f"{o['id']}:{name}".encode()).hexdigest()[:20],
                        "traceId": o["traceId"], "observationId": o["id"],
                        "name": name, "value": score, "dataType": "NUMERIC", "comment": reason,
                    }).raise_for_status()
                    posted += 1
                except Exception as e:
                    print(f"  ! {name} on obs {o.get('id','?')[:8]}: {e}")
        print(f"codified judge: {len(obs)} rag-generate obs × {len(CATALOG)} criteria → {posted} scores posted")


if __name__ == "__main__":
    main()
