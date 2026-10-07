"""B174 — decision-model SHADOW on the incident sweep.

After the sweep's agent run, a decision model is asked which ONE tool the operator should have opened with, and its
pick is compared with the tool qwen actually called first. Nothing acts on the answer — it is evidence, counted in
operator_decide_shadow_total{backend,outcome,confident}, the way the guards ran shadow before they enforced.

Two backends, one API (the Jev / SystemOne `POST /v1/systemone` request shape):
  • jev  — TypeSafe's hosted Jev (PAID from the owner's TypeSafe credit, ~2K input tokens a sweep). Default.
  • clef — Cloudflare's Clef-flash (Apache-2.0) served on demand on rogueone by scripts/clef-flash.sh; point
           OPERATOR_DECIDE_URL at it and set OPERATOR_DECIDE_MODEL=clef-flash. It holds ~8.5 GB of the 16 GB card, so
           it is not left running (it pushes the operator's own model to CPU).

Shadow means: never raises, never changes the sweep, and every failure is COUNTED as outcome="error" — an error is
never recorded as agreement. The API key is sent only over https. Verdict + benchmark: docs/concepts/decision-models.md.
"""
import os
import time
from urllib.parse import urlsplit

import httpx
from prometheus_client import Counter, Histogram

SHADOW = os.getenv("OPERATOR_DECIDE_SHADOW", "false").lower() in ("1", "true", "yes")
URL = os.getenv("OPERATOR_DECIDE_URL", "https://api.typesafe.ai/v1/systemone")
MODEL = os.getenv("OPERATOR_DECIDE_MODEL", "jev-1.13.0")   # pinned, not jev-latest: the evidence is per model
API_KEY = os.getenv("TYPESAFE_API_KEY", "")
TIMEOUT = float(os.getenv("OPERATOR_DECIDE_TIMEOUT", "15"))
CONFIDENT = 0.5            # B174 benchmark: every Clef pick at >= 0.5 confidence was right (38/38)
DESCRIPTION_CHARS = 400    # a tool description is evidence for the choice, not the whole docstring
INSTRUCTIONS = "Which ONE tool should the operator call first to handle the request?"

_SHADOW = Counter("operator_decide_shadow_total",
                  "Decision-model shadow picks vs the operator's actual first tool",
                  ["backend", "outcome", "confident"])
_TOKENS = Counter("operator_decide_input_tokens_total", "Input tokens sent to the decision model", ["backend"])
_SECONDS = Histogram("operator_decide_seconds", "Decision-model call latency", ["backend"],
                     buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15))


def enabled() -> bool:
    return SHADOW


def backend_of(model: str) -> str:
    return "clef" if "clef" in model.lower() else "jev"


def first_tool_called(msgs: list) -> str | None:
    """The first tool the agent called, read off its message trace (duck-typed: any object with `tool_calls`)."""
    for m in msgs:
        for call in getattr(m, "tool_calls", None) or []:
            return call.get("name")
    return None


def request_body(rules: str, request: str, tools: list[tuple[str, str]], model: str) -> dict:
    criteria = {name: " ".join((description or "").split())[:DESCRIPTION_CHARS] for name, description in tools}
    return {"model": model, "state": {"operator_rules": rules, "request": request},
            "questions": {"tool": {"type": "choice", "criteria": criteria, "instructions": INSTRUCTIONS}}}


def headers(url: str, key: str) -> dict:
    """The bearer key rides https only — the Clef server on the LAN is plain http and needs none."""
    h = {"Content-Type": "application/json"}
    if key and urlsplit(url).scheme == "https":
        h["Authorization"] = f"Bearer {key}"
    return h


def outcome(choice: str, actual: str | None) -> str:
    if actual is None:
        return "no_baseline"
    return "agree" if choice == actual else "disagree"


async def shadow(client: httpx.AsyncClient, rules: str, request: str, tools: list[tuple[str, str]],
                 actual: str | None, alert: str) -> dict | None:
    """Ask the decision model, compare with `actual`, count it. Returns the record, or None on ANY failure (counted)."""
    backend = backend_of(MODEL)
    started = time.monotonic()
    try:
        if urlsplit(URL).scheme not in ("http", "https"):
            raise ValueError(f"OPERATOR_DECIDE_URL must be http(s): {URL}")
        r = await client.post(URL, json=request_body(rules, request, tools, MODEL), headers=headers(URL, API_KEY),
                              timeout=TIMEOUT)
        r.raise_for_status()
        reply = r.json()
        answer = reply["answers"]["tool"]
        choice, confidence = answer["choice"], float(answer.get("confidence") or 0.0)
    except Exception as exc:   # a shadow must never break the sweep — but it is never silent either
        _SHADOW.labels(backend, "error", "false").inc()
        print(f"[decide] {backend} shadow failed for {alert}: {exc}", flush=True)
        return None
    seconds = time.monotonic() - started
    result = {"choice": choice, "confidence": confidence, "outcome": outcome(choice, actual), "seconds": seconds}
    _SECONDS.labels(backend).observe(seconds)
    _TOKENS.labels(backend).inc(int((reply.get("usage") or {}).get("input_tokens") or 0))
    _SHADOW.labels(backend, result["outcome"], str(confidence >= CONFIDENT).lower()).inc()
    print(f"[decide] alert={alert} backend={backend} pick={choice} confidence={confidence:.2f} "
          f"operator={actual} outcome={result['outcome']}", flush=True)
    return result
