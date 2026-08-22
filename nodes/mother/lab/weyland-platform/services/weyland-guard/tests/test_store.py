from guardrails.store import record_verdict
from guardrails.verdict import Verdict, Decision, Hook, Mode


def test_record_verdict_inserts(fake_conn):
    v = Verdict(validator="llm_guard.injection", decision=Decision.BLOCK, score=0.9, reason="injection", latency_ms=12)
    record_verdict(fake_conn, request_id="r1", hook=Hook.INPUT, mode=Mode.SHADOW, verdict=v)
    sql, params = fake_conn.executed[0]
    assert "INSERT INTO guardrail_verdicts" in sql
    assert params == ("r1", "input", "llm_guard.injection", "shadow", "block", 0.9, "injection", 12, None)


def test_record_verdict_includes_actor(fake_conn):
    v = Verdict(validator="policy.audit", decision=Decision.PASS, score=None, reason="pipeline/trigger", latency_ms=1)
    record_verdict(fake_conn, request_id="r2", hook=Hook.ACT, mode=Mode.SHADOW, verdict=v, actor="hermes")
    _, params = fake_conn.executed[0]
    assert params[-1] == "hermes"
