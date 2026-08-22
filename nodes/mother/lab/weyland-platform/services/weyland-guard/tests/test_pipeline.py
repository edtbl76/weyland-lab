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
