"""Tests for weyland-mcp-gateway — routing, identity and anti-spoof (2026-10-04, B182 Open WebUI read path).

The gateway is the ONE place identity is established: it validates a Keycloak JWT and sets the identity headers the
backends trust. These pin down the decisions: which backend each path reaches (and that an unconfigured /mcp-memory is
a 404, never a fall-through to the tool-server), who the actor and the user are for a machine vs a human token, and
that a client can never supply its own identity headers. The JWT signature check itself is PyJWT's (not re-tested).

/mcp-memory exists so Open WebUI can recall shared agent memory with EACH PERSON'S own Keycloak login (Open WebUI's
`system_oauth` forwards the user's token) instead of a shared Bifrost virtual key — per-user identity, no stored secret.
"""
import importlib.util
import os

import httpx
import pytest
from starlette.testclient import TestClient

_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
ENV = {"TOOL_SERVER_URL": "http://tool-server:8080", "COMPOSITOR_URL": "http://compositor:8000",
       "MEMORY_COMPOSITOR_URL": "http://memory:8000", "KEYCLOAK_JWKS_URL": "http://kc/certs",
       "KEYCLOAK_ISSUER": "https://keycloak.weyland.lab/realms/weyland"}
OPERATOR = {"azp": "weyland-operator", "preferred_username": "service-account-weyland-operator", "sub": "s1"}
PERSON = {"azp": "open-webui", "preferred_username": "edward", "sub": "u1"}


def _load(monkeypatch, **env):
    for k, v in {**ENV, **env}.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("gateway_under_test", _APP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gw(monkeypatch):
    return _load(monkeypatch)


def test_each_path_reaches_its_backend(gw):
    assert gw.target_url("/mcp-fleet") == "http://compositor:8000/mcp"
    assert gw.target_url("/mcp-memory") == "http://memory:8000/mcp"
    assert gw.target_url("/mcp-memory/") == "http://memory:8000/mcp/"
    assert gw.target_url("/mcp") == "http://tool-server:8080/mcp"
    assert gw.target_url("/mcp-act") == "http://tool-server:8080/mcp-act"


def test_an_unconfigured_memory_route_is_not_found_never_the_tool_server(monkeypatch):
    gw = _load(monkeypatch, MEMORY_COMPOSITOR_URL="")
    assert gw.target_url("/mcp-memory") is None


def test_a_machine_token_is_its_client_and_has_no_user(gw):
    assert gw.identity(OPERATOR) == ("weyland-operator", None)   # unchanged: policy.gate keys on this actor


def test_a_person_is_the_client_they_came_through_plus_their_own_username(gw):
    assert gw.identity(PERSON) == ("open-webui", "edward")


class _Body(httpx.AsyncByteStream):
    """A streamed (not pre-read) body — the gateway relays the backend with aiter_raw(), as the real one streams."""

    async def __aiter__(self):
        yield b'{"ok": true}'


def _client_with(gw, monkeypatch, claims):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, headers={"content-type": "application/json"}, stream=_Body())
    monkeypatch.setattr(gw, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(gw, "_claims_from_bearer", lambda _req: claims)
    return TestClient(gw.app), seen


def test_a_person_reaches_memory_with_identity_set_by_the_gateway_not_the_client(gw, monkeypatch):
    client, seen = _client_with(gw, monkeypatch, PERSON)
    r = client.post("/mcp-memory", json={}, headers={"Authorization": "Bearer t", "X-Forwarded-User": "admin",
                                                     "X-Forwarded-Consumer": "weyland-operator"})
    assert r.status_code == 200
    up = seen[0]
    assert str(up.url) == "http://memory:8000/mcp"
    assert up.headers["x-forwarded-consumer"] == "open-webui"     # spoofed values stripped, validated ones set
    assert up.headers["x-forwarded-user"] == "edward"
    assert "authorization" not in up.headers                       # the user's token never leaves the gateway


def test_a_machine_call_carries_no_user_header_even_if_the_client_sends_one(gw, monkeypatch):
    client, seen = _client_with(gw, monkeypatch, OPERATOR)
    client.post("/mcp-fleet", json={}, headers={"Authorization": "Bearer t", "X-Forwarded-User": "edward"})
    assert seen[0].headers["x-forwarded-consumer"] == "weyland-operator"
    assert "x-forwarded-user" not in seen[0].headers


def test_no_token_is_401_and_nothing_is_forwarded(gw, monkeypatch):
    client, seen = _client_with(gw, monkeypatch, None)
    assert client.post("/mcp-memory", json={}).status_code == 401
    assert seen == []


def test_an_unconfigured_memory_route_answers_404_before_forwarding(monkeypatch):
    gw = _load(monkeypatch, MEMORY_COMPOSITOR_URL="")
    client, seen = _client_with(gw, monkeypatch, PERSON)
    assert client.post("/mcp-memory", json={}, headers={"Authorization": "Bearer t"}).status_code == 404
    assert seen == []
