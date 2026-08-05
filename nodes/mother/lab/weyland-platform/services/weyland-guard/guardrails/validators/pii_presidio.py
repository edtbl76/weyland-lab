"""Scan layer (B117) — PII detection via Microsoft Presidio, called directly.

Replaces the retired `llm_guard.pii` scanner, which already just WRAPPED Presidio (B34) — so this is a near drop-in:
same engine (spaCy `en_core_web_sm` + Presidio's built-in recognizers), no llm-guard. Any PII entity over the score
threshold => BLOCK when enforcing. Carries the B34 calibration for an infra lab — regex-precise
EMAIL/SSN/CC/PHONE/IBAN/BANK + PERSON; IP_ADDRESS / UUID / CRYPTO intentionally dropped (every LAN 192.168.x.x and k8s
UUID would false-positive). PERSON is kept despite the NER mislabeling tech nouns ("Traefik" → PERSON) — the tech-noun
noise is tolerable while this stays SHADOW; context-gate PERSON at promotion. Fail-open; ships SHADOW.
"""
import os

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from ..verdict import Verdict, Decision, Hook

_PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "IBAN_CODE", "US_BANK_NUMBER"]
_THRESHOLD = float(os.environ.get("PII_SCORE_THRESHOLD", "0.5"))
# Presidio defaults to en_core_web_lg; we bake the light en_core_web_sm (B34), so point the NLP engine at it.
_NLP = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}


class PresidioPIIValidator:
    name = "pii.presidio"
    hooks = (Hook.OUTPUT,)

    def __init__(self):
        engine = NlpEngineProvider(nlp_configuration=_NLP).create_engine()
        self._analyzer = AnalyzerEngine(nlp_engine=engine, supported_languages=["en"])

    def check(self, payload: dict, hook: Hook) -> Verdict:
        text = payload.get("answer", "") or ""
        if not text.strip():
            return Verdict(self.name, Decision.PASS, None, "empty text", 0)
        try:
            results = self._analyzer.analyze(text=text, entities=_PII_ENTITIES, language="en",
                                             score_threshold=_THRESHOLD)
        except Exception as exc:            # analyzer failure → fail-open (advisory)
            return Verdict(self.name, Decision.PASS, None, f"presidio error: {exc}", 0)
        if not results:
            return Verdict(self.name, Decision.PASS, None, "no PII", 0)
        top = max(results, key=lambda r: r.score)
        return Verdict(self.name, Decision.BLOCK, float(top.score), f"PII: {top.entity_type} score={top.score:.2f}", 0)
