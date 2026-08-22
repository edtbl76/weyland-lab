from guardrails.config import hook_chain
from guardrails.verdict import Hook, Mode


def test_default_chain_is_shadow():
    chain = hook_chain(Hook.INPUT)            # list of (validator_name, mode)
    assert all(mode == Mode.SHADOW for _, mode in chain)
    names = [n for n, _ in chain]
    # B117 retired the single `llm_guard.injection` scanner (protectai/llm-guard went
    # maintenance-stale) and split it into Prompt Guard 2 for injection and Llama Guard for
    # content safety. Both must be on the INPUT hook.
    assert "prompt_guard.injection" in names
    assert "llama_guard.safety" in names


def test_act_chain_is_audit_shadow():
    # B17+B19 added the act policy GATE alongside the pre-existing audit entry; both ship SHADOW
    # (record-only) until the gateway's `actor` seam is trusted enough to enforce.
    chain = hook_chain(Hook.ACT)
    assert chain == [("policy.audit", Mode.SHADOW), ("policy.gate", Mode.SHADOW)]
