"""B202 — the Realm reads its role prompts from Bifrost's /api at runtime, so from Bifrost v2.2.6 (auth off → setup lock)
it must send X-Bifrost-Setup-Token or every agent silently falls back to its baked prompt. The header comes from
BIFROST_SETUP_TOKEN (read at import, so each case reloads the module) and rides alongside the virtual key, never
replacing it; with no token set, nothing extra is sent (v1.6.7 behaviour unchanged).
"""
import importlib

import httpx
import pytest

import prompts


def _prompt(name, content, role="system"):
    """One list entry in the shape Bifrost v1.6.7 actually returns (observed 2026-10-09, GET /api/prompt-repo/prompts):
    each message is WRAPPED — {"id", "message": {"role", "content"}, "order_index", ...} — under latest_version."""
    return {"id": f"id-{name}", "name": name, "folder": {}, "latest_version": {
        "is_latest": True, "messages": [{"id": 1, "order_index": 0, "message": {"role": role, "content": content}}]}}


class _Reply:
    # Bifrost IGNORES the name/limit query params and returns every prompt, newest first (observed: 280 items, first
    # `loop-scan-triage`), so the role prompt is NOT items[0].
    def raise_for_status(self):
        return None

    def json(self):
        return {"prompts": [_prompt("loop-scan-triage", "a loop", role="user"),
                            _prompt("role-scout", "you are the scout"),
                            _prompt("role-other", "you are someone else")]}


@pytest.fixture
def capture(monkeypatch):
    seen = {}

    def fake_get(url, params=None, headers=None, timeout=None, verify=None):
        seen["url"], seen["headers"] = url, dict(headers or {})
        return _Reply()

    monkeypatch.setattr(httpx, "get", fake_get)
    return seen


def _reload(monkeypatch, token, vk="vk-realm"):
    if token is None:
        monkeypatch.delenv("BIFROST_SETUP_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BIFROST_SETUP_TOKEN", token)
    module = importlib.reload(prompts)
    monkeypatch.setattr(module, "BIFROST_VK", vk)
    return module


def test_the_setup_token_is_sent_with_the_virtual_key(monkeypatch, capture):
    module = _reload(monkeypatch, "t0ken")
    assert module._fetch("scout") == "you are the scout"
    assert capture["headers"] == {"X-Bifrost-Setup-Token": "t0ken", "x-bf-vk": "vk-realm"}
    assert capture["url"].endswith("/api/prompt-repo/prompts")


def test_no_token_sends_no_extra_header(monkeypatch, capture):
    module = _reload(monkeypatch, None)
    module._fetch("scout")
    assert capture["headers"] == {"x-bf-vk": "vk-realm"}


def test_the_role_prompt_is_found_by_exact_name_not_list_position(monkeypatch, capture):
    module = _reload(monkeypatch, None)
    assert module._fetch("scout") == "you are the scout"
    assert module._fetch("other") == "you are someone else"
    assert module._fetch("missing") is None          # absent → the baked fallback, never another agent's prompt
