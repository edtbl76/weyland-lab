"""Classify layer (B115) — the Llama Guard content-safety classifier as a weyland-guard validator.

Where the llm_guard scanners are single-purpose transformers (injection, toxicity, PII), Llama Guard is a
model-based classifier over Meta's full safety taxonomy (violent/non-violent crime, weapons, hate, self-harm,
sexual content, privacy, ...). It runs as a SECOND opinion the Scan layer calls, not a replacement.

Tier 1 (this call) hits the always-on Llama-Guard-3-1B on CPU (mother), served by llama.cpp behind the
`llama-guard` ClusterIP. The GGUF embeds Meta's safety-taxonomy chat template, so we POST a plain `messages`
turn and llama.cpp wraps it — the model replies `safe` or `unsafe\\n<S-category>`. temperature MUST be 0
(Llama Guard is non-deterministic above it). Tier 2 (the on-demand 8B on the rogueone GPU) is a later escalation.

Fail-open, like every guard here: if llama-guard is unreachable or replies oddly, PASS (advisory guards must never
take an answer offline). Ships SHADOW — verdicts are recorded, nothing is blocked, until the FP rate is measured.
"""
import os

import httpx

from ..verdict import Verdict, Decision, Hook

# In-cluster llama-guard svc (unmeshed ClusterIP). A meshed caller (this pod) reaching a sidecar-less workload
# auto-negotiates to plaintext, so the svc URL resolves without TLS. Env-overridable for tier-2 / local runs.
_URL = os.environ.get("LLAMA_GUARD_URL", "http://llama-guard.weyland.svc.cluster.local:8080")


class LlamaGuardValidator:
    name = "llama_guard.safety"
    hooks = (Hook.INPUT, Hook.OUTPUT)

    def __init__(self):
        # httpx.Client is thread-safe; validators run in the pipeline's threadpool, so one shared client is fine.
        # A short timeout keeps a slow/hung classifier from piling up shadow tasks — on timeout we fail-open.
        self._c = httpx.Client(base_url=_URL, timeout=15)

    def check(self, payload: dict, hook: Hook) -> Verdict:
        # INPUT classifies the user prompt; OUTPUT classifies the answer text. We pass it as a single turn — enough
        # to flag unsafe *content* in either; role-aware response grading (user+assistant pair) is a later refinement.
        text = (payload.get("query") if hook == Hook.INPUT else payload.get("answer")) or ""
        if not text.strip():
            return Verdict(self.name, Decision.PASS, None, "empty text", 0)
        try:
            r = self._c.post("/v1/chat/completions", json={
                "model": "llama-guard",   # llama.cpp ignores the id (single loaded model); kept for OpenAI-shape parity
                "messages": [{"role": "user", "content": text}],
                "temperature": 0, "max_tokens": 24})
            r.raise_for_status()
            content = (r.json()["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:                       # unreachable / bad response → fail-open (advisory)
            return Verdict(self.name, Decision.PASS, None, f"llama-guard error: {exc}", 0)

        verdict, _, rest = content.partition("\n")
        label = verdict.strip().lower()
        if label == "unsafe":
            category = rest.strip() or "?"             # e.g. "S1" (Violent Crimes), "S9" (Indiscriminate Weapons)
            return Verdict(self.name, Decision.BLOCK, None, f"unsafe: {category}", 0)
        if label == "safe":
            return Verdict(self.name, Decision.PASS, None, "safe", 0)
        # Unrecognized reply (model drift / non-guard output) → fail-open, but surface it so it's visible in the store.
        return Verdict(self.name, Decision.PASS, None, f"unparsed: {content[:60]!r}", 0)
