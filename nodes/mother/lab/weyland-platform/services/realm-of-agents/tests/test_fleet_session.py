"""Bifrost Agent Logs correlation (B249, 2026-11-19): the Realm's own MCP calls through Bifrost carry the dispatch's
session id as `x-bf-session-id`, so a conversation's tool calls join it in Agent Logs. The tools are loaded once per
process with fixed headers, so the id is added per request by the client's send(), which reads the current session at send time.
fleet.py and obs.py are loaded from their files: conftest stubs both by name."""
import asyncio
import importlib.util
import pathlib
import sys
import types

import httpx

_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, _DIR / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fleet_with_real_obs(monkeypatch):
    obs = _load("realm_obs_under_test", "obs.py")
    monkeypatch.setitem(sys.modules, "obs", obs)
    return _load("realm_fleet_under_test", "fleet.py"), obs


def _sent_headers(client, url="http://bifrost/mcp"):
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json={})
    client._transport = httpx.MockTransport(handler)
    asyncio.run(client.post(url, json={}))
    return seen


def test_a_request_carries_the_current_session_id(monkeypatch):
    fleet, obs = _fleet_with_real_obs(monkeypatch)
    client = fleet.session_aware_client({"x-bf-vk": "vk-1"})

    async def go():
        obs.set_session("ctx-7")
        seen = {}

        def handler(request):
            seen.update(request.headers)
            return httpx.Response(200, json={})
        client._transport = httpx.MockTransport(handler)
        await client.post("http://bifrost/mcp", json={})
        return seen
    seen = asyncio.run(go())
    assert seen["x-bf-session-id"] == "ctx-7" and seen["x-bf-vk"] == "vk-1"


def test_no_session_means_no_header(monkeypatch):
    fleet, _ = _fleet_with_real_obs(monkeypatch)
    seen = _sent_headers(fleet.session_aware_client({"x-bf-vk": "vk-1"}))
    assert "x-bf-session-id" not in seen and seen["x-bf-vk"] == "vk-1"


def test_obs_reports_the_current_session(monkeypatch):
    obs = _load("realm_obs_only", "obs.py")

    async def go():
        assert obs.current_session() is None
        obs.set_session("s-1")
        return obs.current_session()
    assert asyncio.run(go()) == "s-1"


def test_a_streamed_request_carries_it_too(monkeypatch):
    """The MCP streamable-HTTP transport sends with client.stream(), not post(): the header must ride that path too."""
    fleet, obs = _fleet_with_real_obs(monkeypatch)
    client = fleet.session_aware_client({"x-bf-vk": "vk-1"})

    async def go():
        obs.set_session("ctx-9")
        seen = {}

        def handler(request):
            seen.update(request.headers)
            return httpx.Response(200, text="event: message\n\n")
        client._transport = httpx.MockTransport(handler)
        async with client.stream("POST", "http://bifrost/mcp", json={}) as resp:
            await resp.aread()
        return seen
    assert asyncio.run(go())["x-bf-session-id"] == "ctx-9"
