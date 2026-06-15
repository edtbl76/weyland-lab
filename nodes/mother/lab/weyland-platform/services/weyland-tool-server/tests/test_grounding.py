from guardrails.verdict import Decision, Hook


class _FakeCE:
    def __init__(self, score):
        self._s = score

    def predict(self, pairs):
        return [self._s for _ in pairs]


def test_grounding_flags_unsupported():
    from guardrails.validators.grounding import GroundingValidator
    v = GroundingValidator(cross_encoder=_FakeCE(0.05), threshold=0.5)
    verdict = v.check({"answer": "X", "sources": [{"content": "unrelated"}]}, Hook.OUTPUT)
    assert verdict.decision == Decision.FLAG and verdict.score == 0.05


def test_grounding_passes_when_supported():
    from guardrails.validators.grounding import GroundingValidator
    v = GroundingValidator(cross_encoder=_FakeCE(0.92), threshold=0.5)
    verdict = v.check({"answer": "X", "sources": [{"content": "X is true"}]}, Hook.OUTPUT)
    assert verdict.decision == Decision.PASS


def test_grounding_passes_when_no_sources():
    from guardrails.validators.grounding import GroundingValidator
    v = GroundingValidator(cross_encoder=_FakeCE(0.0), threshold=0.5)
    verdict = v.check({"answer": "X", "sources": []}, Hook.OUTPUT)
    assert verdict.decision == Decision.PASS


class _FakeNLICE:
    """Models a real NLI cross-encoder: 3 logits per pair [contradiction, entailment, neutral]."""

    def __init__(self, rows):
        self._rows = rows

    def predict(self, pairs):
        return self._rows[: len(pairs)]


def test_grounding_nli_passes_on_high_entailment():
    # entailment logit dominates -> softmax entailment prob ~0.99 -> PASS
    v = __import__("guardrails.validators.grounding", fromlist=["GroundingValidator"]).GroundingValidator(
        cross_encoder=_FakeNLICE([[0.1, 5.0, 0.1]]), threshold=0.5
    )
    verdict = v.check({"answer": "X", "sources": [{"content": "X is true"}]}, Hook.OUTPUT)
    assert verdict.decision == Decision.PASS and verdict.score > 0.9


def test_grounding_nli_flags_on_contradiction():
    # contradiction logit dominates -> entailment prob low -> FLAG (this is the case the
    # old float(max(...)) bug silently passed)
    v = __import__("guardrails.validators.grounding", fromlist=["GroundingValidator"]).GroundingValidator(
        cross_encoder=_FakeNLICE([[5.0, 0.1, 0.1]]), threshold=0.5
    )
    verdict = v.check({"answer": "X", "sources": [{"content": "unrelated"}]}, Hook.OUTPUT)
    assert verdict.decision == Decision.FLAG and verdict.score < 0.1
