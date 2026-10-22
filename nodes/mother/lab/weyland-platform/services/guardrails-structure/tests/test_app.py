"""The Ollama front-door token goes only to the configured Ollama (B211, 2026-10-22).

/structure/judge-scores takes `api_base` from the request, so a caller can name any URL. Attaching OLLAMA_API_KEY to a
caller-chosen base would hand the token to whoever that URL belongs to. The token goes with the call only when the
resolved base is the configured Ollama (scheme, host and port); any other base gets the old placeholder, which the
front door refuses. The Guard is stubbed: what is tested is which key app.py hands it.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://192.168.1.230:11434")
    monkeypatch.setenv("OLLAMA_API_KEY", "tok-123")
    sys.modules.pop("app", None)
    import app as mod
    seen = {}

    class _Guard:
        def parse(self, **kw):
            seen.update(kw)
            raise RuntimeError("stub")

    monkeypatch.setattr(mod, "_get_guard", lambda: _Guard())
    mod.seen = seen
    return mod


def _judge(mod, api_base):
    mod.judge_scores(mod.JudgeScoresRequest(raw="x", model="qwen3:14b", api_base=api_base))
    return mod.seen


@pytest.mark.parametrize("api_base", [None, "http://192.168.1.230:11434", "http://192.168.1.230:11434/v1",
                                      "http://192.168.1.230:11434/"])
def test_the_configured_ollama_gets_the_token(app, api_base):
    assert _judge(app, api_base)["api_key"] == "tok-123"


@pytest.mark.parametrize("api_base", ["http://attacker.example:11434", "http://192.168.1.230:8080",
                                      "https://192.168.1.230:11434", "http://192.168.1.230.attacker.example:11434"])
def test_any_other_base_never_gets_the_token(app, api_base):
    seen = _judge(app, api_base)
    assert seen["api_key"] != "tok-123"
    assert seen["api_base"].startswith(api_base.rstrip("/"))
