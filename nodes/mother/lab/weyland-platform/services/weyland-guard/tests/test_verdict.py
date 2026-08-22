from guardrails.verdict import Verdict, Decision, Hook, Mode


def test_verdict_fields():
    v = Verdict(validator="x", decision=Decision.PASS, score=0.1, reason="ok", latency_ms=5)
    assert v.decision == "pass"
    assert v.score == 0.1


def test_enums_are_str():
    assert Hook.INPUT == "input"
    assert Mode.SHADOW == "shadow"
