from guardrails.metrics import observe
from guardrails.verdict import Verdict, Decision, Hook, Mode
from prometheus_client import REGISTRY


def test_observe_increments_counter():
    v = Verdict(validator="g", decision=Decision.FLAG, score=0.5, reason="r", latency_ms=3)
    observe(Hook.OUTPUT, Mode.SHADOW, v)
    val = REGISTRY.get_sample_value(
        "guardrail_verdicts_total",
        {"validator": "g", "hook": "output", "decision": "flag", "mode": "shadow"},
    )
    assert val == 1.0
