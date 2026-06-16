import asyncio
import time
from .verdict import Verdict, Decision, Hook, Mode


class GuardrailPipeline:
    """Runs the configured validator chain for a hook.

    SHADOW/OFF: never alters the response. SHADOW runs the validator fire-and-forget in a
    threadpool (validators are CPU-bound) and records the verdict — ~zero added response latency.
    FLAG/BLOCK: run synchronously (they must, to alter the response) and record inline.
    Returns the first BLOCK verdict (block mode) else None.

    Shadow tasks are tracked in `_pending`; `drain()` awaits them (used at shutdown and in tests).
    In production the long-lived event loop drains them naturally.
    """

    def __init__(self, validators, chain_for, record):
        self._validators = validators          # name -> Validator
        self._chain_for = chain_for            # hook -> [(name, Mode)]
        self._record = record                  # callable(**kwargs)
        self._pending: set = set()

    def _run_one(self, name: str, payload: dict, hook: Hook) -> Verdict:
        v = self._validators.get(name)
        if v is None:                          # configured but not loaded (e.g. model unavailable)
            return Verdict(name, Decision.PASS, None, "validator not loaded", 0)
        t0 = time.monotonic()
        try:
            verdict = v.check(payload, hook)
        except Exception as exc:               # a guard must never break the request
            return Verdict(name, Decision.PASS, None, f"validator error: {exc}", 0)
        verdict.latency_ms = int((time.monotonic() - t0) * 1000)
        return verdict

    async def _shadow(self, name: str, payload: dict, hook: Hook, request_id: str, actor: str | None) -> None:
        loop = asyncio.get_event_loop()
        verdict = await loop.run_in_executor(None, self._run_one, name, payload, hook)
        self._record(hook=hook, mode=Mode.SHADOW, verdict=verdict, request_id=request_id, actor=actor)

    async def run(self, hook: Hook, request_id: str, payload: dict, actor: str | None = None):
        loop = asyncio.get_event_loop()
        for name, mode in self._chain_for(hook):
            if mode == Mode.OFF:
                continue
            if mode == Mode.SHADOW:
                task = asyncio.create_task(self._shadow(name, payload, hook, request_id, actor))
                self._pending.add(task)
                task.add_done_callback(self._pending.discard)
                continue
            # FLAG / BLOCK — synchronous (they alter the response, so must complete inline)
            verdict = await loop.run_in_executor(None, self._run_one, name, payload, hook)
            self._record(hook=hook, mode=mode, verdict=verdict, request_id=request_id, actor=actor)
            if mode == Mode.BLOCK and verdict.decision == Decision.BLOCK:
                return verdict
        return None

    async def drain(self) -> None:
        if self._pending:
            await asyncio.gather(*list(self._pending), return_exceptions=True)
