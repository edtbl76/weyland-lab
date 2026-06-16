from guardrails.config import hook_chain
from guardrails.verdict import Hook, Mode


def test_default_chain_is_shadow():
    chain = hook_chain(Hook.INPUT)            # list of (validator_name, mode)
    assert all(mode == Mode.SHADOW for _, mode in chain)
    names = [n for n, _ in chain]
    assert "llm_guard.injection" in names


def test_act_chain_is_audit_shadow():
    chain = hook_chain(Hook.ACT)
    assert chain == [("policy.audit", Mode.SHADOW)]
