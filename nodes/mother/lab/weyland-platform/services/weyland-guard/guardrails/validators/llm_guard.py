from llm_guard.input_scanners import PromptInjection
from llm_guard.output_scanners import Toxicity, Sensitive
from ..verdict import Verdict, Decision, Hook


# Map an llm_guard (is_valid, risk_score) result to a Verdict. is_valid False => block when enforcing.
def _verdict(name: str, is_valid: bool, score: float, kind: str) -> Verdict:
    decision = Decision.PASS if is_valid else Decision.BLOCK
    return Verdict(name, decision, float(score), f"{kind} risk={score}", 0)


class InjectionValidator:
    name = "llm_guard.injection"
    hooks = (Hook.INPUT,)

    def __init__(self):
        self._s = PromptInjection()

    def check(self, payload: dict, hook: Hook) -> Verdict:
        text = payload.get("query", "") or ""
        _, is_valid, score = self._s.scan(text)
        return _verdict(self.name, is_valid, score, "injection")


class ToxicityValidator:
    name = "llm_guard.toxicity"
    hooks = (Hook.OUTPUT,)

    def __init__(self):
        self._s = Toxicity()

    def check(self, payload: dict, hook: Hook) -> Verdict:
        text = payload.get("answer", "") or ""
        _, is_valid, score = self._s.scan("", text)
        return _verdict(self.name, is_valid, score, "toxicity")


# B34: PII entities tuned for an INFRA lab. llm_guard's Sensitive defaults include IP_ADDRESS + UUID,
# which would false-positive on every LAN 192.168.x.x and every k8s UUID in a RAG answer — pure noise.
# Keep only the genuinely-sensitive entities that match the export / PII-data triggers this guard exists for.
_PII_ENTITIES = [
    "PERSON", "EMAIL_ADDRESS", "EMAIL_ADDRESS_RE", "PHONE_NUMBER",
    "US_SSN", "US_SSN_RE", "CREDIT_CARD", "CREDIT_CARD_RE",
    "IBAN_CODE", "US_BANK_NUMBER", "CRYPTO",
]


class PIIValidator:
    name = "llm_guard.pii"
    hooks = (Hook.OUTPUT,)

    def __init__(self):
        self._s = Sensitive(entity_types=_PII_ENTITIES)

    def check(self, payload: dict, hook: Hook) -> Verdict:
        text = payload.get("answer", "") or ""
        _, is_valid, score = self._s.scan("", text)
        return _verdict(self.name, is_valid, score, "pii")
