"""Tests for Gná, the dispatcher's routing decision (realm-of-agents/router.py).

`classify` turns a free-text task into a single roster key via a fast LLM, and MUST fail safe to 'odin' on any
unparseable/unknown/errored answer (a mis-route sends work to a key with no agent). We stub the brain to return a
fixture reply and assert the CHOSEN KEY — the real decision — never a mock call. The live LLM + the run_lead/
run_solo handoff are exercised in the running system.
"""
import asyncio

import router   # conftest stubs llm/obs/realms/agents siblings; roster (the real key set) stays real


def _brain_returning(content):
    class _Resp:
        def __init__(self, c):
            self.content = c

    class _Brain:
        async def ainvoke(self, _messages, _cfg):
            return _Resp(content)

    return lambda _alias: _Brain()


def test_classify_returns_the_chosen_roster_key(monkeypatch):
    monkeypatch.setattr(router, "brain", _brain_returning("heimdall"))
    assert asyncio.run(router.classify("lock down the gateway auth")) == "heimdall"


def test_classify_strips_punctuation_and_lowercases(monkeypatch):
    monkeypatch.setattr(router, "brain", _brain_returning("  Heimdall.\n"))
    assert asyncio.run(router.classify("x")) == "heimdall"


def test_classify_unknown_key_fails_safe_to_odin(monkeypatch):
    monkeypatch.setattr(router, "brain", _brain_returning("not-a-real-agent"))
    assert asyncio.run(router.classify("x")) == "odin"


def test_classify_empty_reply_fails_safe_to_odin(monkeypatch):
    monkeypatch.setattr(router, "brain", _brain_returning(""))
    assert asyncio.run(router.classify("x")) == "odin"


def test_classify_brain_error_fails_safe_to_odin(monkeypatch):
    def _boom(_alias):
        raise RuntimeError("no brain")
    monkeypatch.setattr(router, "brain", _boom)
    assert asyncio.run(router.classify("x")) == "odin"


def test_classify_takes_first_token_only(monkeypatch):
    monkeypatch.setattr(router, "brain", _brain_returning("odin — because it orchestrates"))
    assert asyncio.run(router.classify("x")) == "odin"
