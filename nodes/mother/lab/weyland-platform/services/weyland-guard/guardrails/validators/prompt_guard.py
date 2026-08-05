"""Scan layer (B117) — prompt-injection / jailbreak detection via Meta Llama Prompt Guard 2.

Replaces the retired `llm_guard.injection` scanner (protectai/llm-guard, maintenance-stale after the Palo Alto
acquisition). Prompt Guard 2 is a small DeBERTa sequence classifier (86M/22M) — NOT a generative model, so it runs
IN-PROCESS via a `transformers` text-classification pipeline (like the grounding CrossEncoder), baked into the image and
loaded offline. Binary: benign vs malicious; malicious-probability over the threshold => BLOCK when enforcing.

Fail-open, like every guard here: a load/scan failure PASSes (an advisory guard must never take a request offline).
Ships SHADOW — verdicts recorded, nothing blocked, until the false-positive rate is measured on real traffic.
"""
import os

from transformers import pipeline

from ..verdict import Verdict, Decision, Hook

_MODEL = os.environ.get("PROMPT_GUARD_MODEL", "project-free-llama/Llama-Prompt-Guard-2-22M")
_THRESHOLD = float(os.environ.get("PROMPT_GUARD_THRESHOLD", "0.5"))
_BENIGN = {"benign", "label_0", "0"}   # anything else (malicious / injection / jailbreak / label_1) counts as an attack


class PromptGuardValidator:
    name = "prompt_guard.injection"
    hooks = (Hook.INPUT,)

    def __init__(self):
        # top_k=None returns every class's score; truncation keeps long prompts within Prompt Guard's 512-token window.
        self._pipe = pipeline("text-classification", model=_MODEL, top_k=None, truncation=True)

    def check(self, payload: dict, hook: Hook) -> Verdict:
        text = payload.get("query", "") or ""
        if not text.strip():
            return Verdict(self.name, Decision.PASS, None, "empty text", 0)
        try:
            raw = self._pipe(text)
            # top_k=None: a single input can come back as [[{label,score},...]] or [{label,score},...] by version.
            scores = raw[0] if raw and isinstance(raw[0], list) else raw
            malicious = max((s["score"] for s in scores if s["label"].strip().lower() not in _BENIGN), default=0.0)
        except Exception as exc:            # load/scan failure → fail-open (advisory)
            return Verdict(self.name, Decision.PASS, None, f"prompt-guard error: {exc}", 0)
        decision = Decision.BLOCK if malicious >= _THRESHOLD else Decision.PASS
        return Verdict(self.name, decision, float(malicious), f"injection risk={malicious:.3f}", 0)
