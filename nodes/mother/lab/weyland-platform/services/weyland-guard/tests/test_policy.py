from guardrails.validators.policy import AuditValidator
from guardrails.verdict import Decision, Hook


def test_audit_always_passes_and_captures_action():
    v = AuditValidator().check({"tool": "pipeline/trigger", "params": {"job_name": "weyland_ingestion_job"}}, Hook.ACT)
    assert v.decision == Decision.PASS
    assert "pipeline/trigger" in v.reason and "weyland_ingestion_job" in v.reason


def test_audit_handles_no_params():
    v = AuditValidator().check({"tool": "evals/run"}, Hook.ACT)
    assert v.decision == Decision.PASS and v.reason == "evals/run"


# ── PolicyGateValidator — the ENFORCING act gate (B17+B19) ──────────────────────────────────────
# Every case here is a security assertion: the gate decides what act calls are BLOCKED vs ALLOWED.
# A regression is not a coverage number, it is the guard admitting something it should refuse. The
# gate was at 41% coverage (all 5 decision branches + the rate limiter untested); these cover them.
from guardrails.validators.policy import PolicyGateValidator, _load_policy
from guardrails.verdict import Decision

_POLICY = {"weyland-operator": {"tools": ["*"], "rate_per_min": 30},
           "reports-agent": {"tools": ["evals/run"], "rate_per_min": 2}}


def _gate():
    return PolicyGateValidator(policy=_POLICY)


def test_gate_blocks_an_act_with_no_actor():
    # An act without an authenticated identity bypassed the MCP gateway — the most important block.
    v = _gate().check({"tool": "pipeline/trigger"}, Hook.ACT)
    assert v.decision == Decision.BLOCK
    assert "no actor" in v.reason


def test_gate_blocks_an_unknown_actor():
    v = _gate().check({"tool": "evals/run", "actor": "stranger"}, Hook.ACT)
    assert v.decision == Decision.BLOCK
    assert "not in the act allowlist" in v.reason


def test_gate_blocks_a_tool_the_actor_may_not_call():
    # reports-agent is allowlisted for evals/run ONLY — pipeline/trigger must be refused.
    v = _gate().check({"tool": "pipeline/trigger", "actor": "reports-agent"}, Hook.ACT)
    assert v.decision == Decision.BLOCK
    assert "may not call" in v.reason


def test_gate_allows_a_permitted_actor_tool_pair():
    v = _gate().check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT)
    assert v.decision == Decision.PASS
    assert "allow" in v.reason


def test_gate_wildcard_actor_may_call_anything():
    # weyland-operator has "*" — any tool passes (up to the rate limit).
    v = _gate().check({"tool": "some/brand-new-tool", "actor": "weyland-operator"}, Hook.ACT)
    assert v.decision == Decision.PASS


def test_gate_rate_limit_blocks_after_the_cap():
    # reports-agent is capped at 2/min. The 3rd call in the window must block, and the reason must
    # say WHY — a bare block would be indistinguishable from an allowlist miss.
    g = _gate()
    assert g.check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT).decision == Decision.PASS
    assert g.check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT).decision == Decision.PASS
    third = g.check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT)
    assert third.decision == Decision.BLOCK
    assert "rate limit" in third.reason


def test_rate_limit_is_per_actor_not_global():
    # One actor exhausting its cap must not block a different actor — the window is keyed by actor.
    g = _gate()
    g.check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT)
    g.check({"tool": "evals/run", "actor": "reports-agent"}, Hook.ACT)
    # reports-agent is now at its cap; weyland-operator must still be allowed.
    assert g.check({"tool": "x", "actor": "weyland-operator"}, Hook.ACT).decision == Decision.PASS


def test_load_policy_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("GUARD_ACT_POLICY", raising=False)
    pol = _load_policy()
    assert "weyland-operator" in pol


def test_load_policy_reads_valid_env_json(monkeypatch):
    monkeypatch.setenv("GUARD_ACT_POLICY", '{"agent-x": {"tools": ["a"], "rate_per_min": 5}}')
    pol = _load_policy()
    assert pol == {"agent-x": {"tools": ["a"], "rate_per_min": 5}}


def test_load_policy_falls_back_on_malformed_env(monkeypatch):
    # Malformed override must NOT crash the guard — it falls back to the built-in default, so a
    # fat-fingered env var degrades to "safe defaults", never "guard down".
    monkeypatch.setenv("GUARD_ACT_POLICY", "{not valid json")
    pol = _load_policy()
    assert "weyland-operator" in pol
