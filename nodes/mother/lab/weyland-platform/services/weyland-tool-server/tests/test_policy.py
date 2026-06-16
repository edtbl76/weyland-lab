from guardrails.validators.policy import AuditValidator
from guardrails.verdict import Decision, Hook


def test_audit_always_passes_and_captures_action():
    v = AuditValidator().check({"tool": "pipeline/trigger", "params": {"job_name": "weyland_ingestion_job"}}, Hook.ACT)
    assert v.decision == Decision.PASS
    assert "pipeline/trigger" in v.reason and "weyland_ingestion_job" in v.reason


def test_audit_handles_no_params():
    v = AuditValidator().check({"tool": "evals/run"}, Hook.ACT)
    assert v.decision == Decision.PASS and v.reason == "evals/run"
