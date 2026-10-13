import asyncio
from guardrails.pipeline import GuardrailPipeline
from guardrails.verdict import Verdict, Decision, Hook, Mode


class _StubValidator:
    name = "stub"
    hooks = (Hook.INPUT,)

    def __init__(self, decision):
        self._d = decision

    def check(self, payload, hook):
        return Verdict("stub", self._d, 1.0, "r", 1)


def test_shadow_records_but_does_not_block():
    recorded = []
    pipe = GuardrailPipeline(
        validators={"stub": _StubValidator(Decision.BLOCK)},
        chain_for=lambda hook: [("stub", Mode.SHADOW)] if hook == Hook.INPUT else [],
        record=lambda **kw: recorded.append(kw),
    )

    async def go():
        blocked = await pipe.run(Hook.INPUT, request_id="r1", payload={"query": "x"})
        assert blocked is None              # shadow never blocks
        await pipe.drain()                  # let the fire-and-forget shadow task finish

    asyncio.run(go())
    assert any(r["verdict"].decision == Decision.BLOCK for r in recorded)


def test_block_mode_returns_block():
    pipe = GuardrailPipeline(
        validators={"stub": _StubValidator(Decision.BLOCK)},
        chain_for=lambda hook: [("stub", Mode.BLOCK)] if hook == Hook.INPUT else [],
        record=lambda **kw: None,
    )
    blocked = asyncio.run(pipe.run(Hook.INPUT, request_id="r1", payload={"query": "x"}))
    assert blocked is not None and blocked.decision == Decision.BLOCK


def test_actor_threaded_to_record():
    recorded = []
    pipe = GuardrailPipeline(
        validators={"stub": _StubValidator(Decision.PASS)},
        chain_for=lambda hook: [("stub", Mode.SHADOW)] if hook == Hook.ACT else [],
        record=lambda **kw: recorded.append(kw),
    )

    async def go():
        await pipe.run(Hook.ACT, request_id="r1", payload={"tool": "x"}, actor="hermes")
        await pipe.drain()

    asyncio.run(go())
    assert recorded and recorded[0]["actor"] == "hermes"


# B207 (2026-10-13): authority fails CLOSED inside the guard too. An enforcing ACT validator that raises, or that is
# configured but not loaded, used to count as PASS — so a crashing policy.gate would have ALLOWED every act.
class _Raises:
    name = "policy.gate"
    hooks = (Hook.ACT, Hook.INPUT)

    def check(self, payload, hook):
        raise RuntimeError("policy file unreadable")


def _run(hook, chain, validators):
    recorded = []
    pipe = GuardrailPipeline(validators=validators, chain_for=lambda h: chain if h == hook else [],
                             record=lambda **kw: recorded.append(kw))
    return asyncio.run(pipe.run(hook, request_id="r1", payload={"tool": "x"}, actor="a")), recorded


def test_a_raising_act_validator_in_block_mode_blocks():
    blocked, recorded = _run(Hook.ACT, [("policy.gate", Mode.BLOCK)], {"policy.gate": _Raises()})
    assert blocked is not None and blocked.decision == Decision.BLOCK
    assert blocked.reason == "validator error: policy file unreadable"
    assert recorded[0]["verdict"].decision == Decision.BLOCK          # the record says what happened


def test_an_unloaded_act_validator_in_block_mode_blocks():
    blocked, _ = _run(Hook.ACT, [("policy.gate", Mode.BLOCK)], {})
    assert blocked is not None and blocked.decision == Decision.BLOCK and blocked.reason == "validator not loaded"


def test_a_raising_content_validator_still_passes():
    blocked, recorded = _run(Hook.INPUT, [("policy.gate", Mode.BLOCK)], {"policy.gate": _Raises()})
    assert blocked is None                                             # content fails open
    assert recorded[0]["verdict"].decision == Decision.PASS


def test_a_raising_act_validator_in_shadow_mode_only_records():
    async def go():
        recorded = []
        pipe = GuardrailPipeline(validators={"policy.gate": _Raises()},
                                 chain_for=lambda h: [("policy.gate", Mode.SHADOW)] if h == Hook.ACT else [],
                                 record=lambda **kw: recorded.append(kw))
        blocked = await pipe.run(Hook.ACT, request_id="r1", payload={"tool": "x"})
        await pipe.drain()
        return blocked, recorded
    blocked, recorded = asyncio.run(go())
    assert blocked is None                                             # shadow never blocks, even on ACT
    assert recorded[0]["verdict"].decision == Decision.BLOCK           # but the would-be refusal is recorded
